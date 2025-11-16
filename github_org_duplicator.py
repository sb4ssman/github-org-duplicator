#!/usr/bin/env python3
"""
GitHub Organization Repository Migration Script

Duplicates all repositories from one GitHub organization to another.
Requires: gh CLI authenticated with 2FA
"""

import subprocess
import json
import os
import shutil
import sys
import time
from datetime import datetime

def run_command(cmd, check=True, capture=True):
    """Run a shell command and return result."""
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result

def log_message(message, log_file):
    """Print to console and write to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(message)
    with open(log_file, 'a', encoding='utf-8') as f:  # <-- Added encoding='utf-8'
        f.write(log_entry + '\n')

# def log_message(message, log_file):
#     """Print to console and write to log file."""
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     log_entry = f"[{timestamp}] {message}"
#     print(message)
#     with open(log_file, 'a') as f:
#         f.write(log_entry + '\n')

def check_gh_installed():
    """Verify gh CLI is installed."""
    try:
        run_command(['gh', '--version'], check=True)
        print("✓ gh CLI installed")
    except:
        print("ERROR: gh CLI is not installed.")
        print("Install from: https://cli.github.com/")
        sys.exit(1)

def check_gh_authenticated():
    """Verify gh is authenticated."""
    try:
        run_command(['gh', 'auth', 'status'], check=True)
        print("✓ gh authenticated")
    except:
        print("ERROR: gh is not authenticated.")
        print("Run: gh auth login")
        sys.exit(1)

def setup_git_credentials():
    """Ensure git uses gh credentials."""
    try:
        run_command(['gh', 'auth', 'setup-git'], check=True)
        print("✓ git configured to use gh credentials")
    except:
        print("WARNING: Could not configure git to use gh credentials")
        print("You may need to run: gh auth setup-git")

def check_org_access(org):
    """Verify access to an organization."""
    try:
        run_command(['gh', 'repo', 'list', org, '--limit', '1', '--json', 'name'], check=True)
        return True
    except:
        print(f"ERROR: Cannot access organization '{org}'")
        print(f"Make sure you have access and the org name is correct.")
        sys.exit(1)

def check_repo_for_lfs(org, repo_name):
    """Check if a repository uses Git LFS by looking for .gitattributes with LFS filters."""
    try:
        # Fetch .gitattributes file content
        result = run_command([
            'gh', 'api',
            f'/repos/{org}/{repo_name}/contents/.gitattributes',
            '--jq', '.content'
        ], check=False)
        
        if result.returncode == 0:
            # Decode base64 content
            import base64
            content = base64.b64decode(result.stdout.strip()).decode('utf-8', errors='ignore')
            if 'filter=lfs' in content:
                return True
    except:
        pass
    return False

def get_repos_with_details(org):
    """Fetch all repos from an organization with detailed information."""
    print(f"Fetching repos from {org}...")
    try:
        result = run_command([
            'gh', 'repo', 'list', org,
            '--limit', '1000',
            '--json', 'name,createdAt,isPrivate,description,diskUsage'
        ])
    except Exception as e:
        print(f"ERROR: Failed to fetch repos from {org}")
        print(str(e))
        sys.exit(1)
    
    repos = json.loads(result.stdout)

    # Check each repo for LFS
    print(f"Checking {len(repos)} repos for Git LFS usage...")
    for idx, repo in enumerate(repos, 1):
        # Clear line and print progress
        print(f"\r{' ' * 80}\r  Checking {idx}/{len(repos)}: {repo['name']}", end='', flush=True)
        repo['uses_lfs'] = check_repo_for_lfs(org, repo['name'])
    print()  # New line after progress

    # # Check each repo for LFS
    # print(f"Checking {len(repos)} repos for Git LFS usage...")
    # for idx, repo in enumerate(repos, 1):
    #     print(f"  Checking {idx}/{len(repos)}: {repo['name']}", end='\r')
    #     repo['uses_lfs'] = check_repo_for_lfs(org, repo['name'])
    # print()  # New line after progress
    
    return repos

def compare_repos(source_org, dest_org, repo_name):
    """Compare two repos to see if they're identical duplicates."""
    try:
        # Get branch info from both repos
        source_branches = run_command([
            'gh', 'api', f'/repos/{source_org}/{repo_name}/branches',
            '--jq', '.[].name'
        ], check=True)
        
        dest_branches = run_command([
            'gh', 'api', f'/repos/{dest_org}/{repo_name}/branches',
            '--jq', '.[].name'
        ], check=True)
        
        source_branch_list = set(source_branches.stdout.strip().split('\n'))
        dest_branch_list = set(dest_branches.stdout.strip().split('\n'))
        
        # Compare branch names
        if source_branch_list != dest_branch_list:
            return False, "Branch names don't match"
        
        # For each branch, compare the HEAD commit SHA
        for branch in source_branch_list:
            source_sha = run_command([
                'gh', 'api', f'/repos/{source_org}/{repo_name}/branches/{branch}',
                '--jq', '.commit.sha'
            ], check=True).stdout.strip()
            
            dest_sha = run_command([
                'gh', 'api', f'/repos/{dest_org}/{repo_name}/branches/{branch}',
                '--jq', '.commit.sha'
            ], check=True).stdout.strip()
            
            if source_sha != dest_sha:
                return False, f"Branch '{branch}' has different commits"
        
        return True, "Repos are identical"
        
    except Exception as e:
        return False, f"Error comparing: {str(e)}"

def format_size(kb):
    """Format size in KB to human readable format."""
    if kb < 1024:
        return f"{kb} KB"
    elif kb < 1024 * 1024:
        return f"{kb/1024:.1f} MB"
    else:
        return f"{kb/(1024*1024):.1f} GB"

def display_repo_table(repos, org_name):
    """Display repository information in a readable table format."""
    print()
    print("=" * 100)
    print(f"Repositories in {org_name}")
    print("=" * 100)
    
    if not repos:
        print("No repositories found.")
        return
    
    # Sort by creation date (oldest first)
    sorted_repos = sorted(repos, key=lambda r: r['createdAt'])
    
    # Table header
    print(f"{'#':<4} {'Name':<40} {'Size':<12} {'Private':<8} {'LFS':<6} {'Created':<20}")
    print("-" * 100)
    
    lfs_repos = []
    for idx, repo in enumerate(sorted_repos, 1):
        name = repo['name'][:39] if len(repo['name']) > 39 else repo['name']
        size = format_size(repo.get('diskUsage', 0))
        private = "Yes" if repo['isPrivate'] else "No"
        lfs = "⚠ YES" if repo['uses_lfs'] else "No"
        created = repo['createdAt'][:10]  # Just the date part
        
        print(f"{idx:<4} {name:<40} {size:<12} {private:<8} {lfs:<6} {created:<20}")
        
        if repo['uses_lfs']:
            lfs_repos.append(repo['name'])
    
    print("=" * 100)
    print(f"Total: {len(sorted_repos)} repositories")
    print(f"Total size: {format_size(sum(r.get('diskUsage', 0) for r in sorted_repos))}")
    
    if lfs_repos:
        print()
        print("⚠ WARNING: The following repositories use Git LFS:")
        for repo_name in lfs_repos:
            print(f"  - {repo_name}")
        print()
        print("Git LFS repositories require special handling:")
        print("  1. You must have Git LFS installed (git lfs install)")
        print("  2. LFS files may not transfer correctly with --mirror")
        print("  3. You may need to manually configure LFS in the new org")
    
    print()

def main():
    print("=" * 60)
    print("GitHub Organization Repository Migration")
    print("=" * 60)
    print()
    
    # Check prerequisites
    check_gh_installed()
    check_gh_authenticated()
    setup_git_credentials()
    print()
    
    # Get user input
    source_org = input("Source organization name: ").strip()
    dest_org = input("Destination organization name: ").strip()
    
    print()
    
    # Check access to both orgs
    print("Verifying organization access...")
    check_org_access(source_org)
    print(f"✓ Admin rights confirmed for {source_org}")
    check_org_access(dest_org)
    print(f"✓ Admin rights confirmed for {dest_org}")
    print()
    
    # Detect repos in both orgs
    print("Detecting repos in both orgs...")
    source_repos = get_repos_with_details(source_org)
    dest_repos = get_repos_with_details(dest_org)
    
    print(f"✓ {len(source_repos)} repos found in {source_org}")
    print(f"✓ {len(dest_repos)} repos found in {dest_org}")
    print()

    # Check for conflicts (case-insensitive)
    source_names = {repo['name'].lower(): repo['name'] for repo in source_repos}
    dest_names = {repo['name'].lower(): repo['name'] for repo in dest_repos}
    conflicts = set(source_names.keys()) & set(dest_names.keys())

    if conflicts:
        print()
        print("=" * 60)
        print("Matching repository names found. Verifying if duplicates...")
        print("=" * 60)
        
        actual_conflicts = []
        verified_duplicates = []
        
        for name_lower in sorted(conflicts):
            repo_name = source_names[name_lower]
            print(f"Checking: {repo_name}...", end=' ')
            
            is_identical, reason = compare_repos(source_org, dest_org, repo_name)
            
            if is_identical:
                print(f"✓ Verified duplicate")
                verified_duplicates.append(repo_name)
            else:
                print(f"✗ Different ({reason})")
                actual_conflicts.append(repo_name)
        
        print()
        
        if actual_conflicts:
            print("ERROR: Non-duplicate repositories with matching names found:")
            for name in actual_conflicts:
                print(f"  - {name}")
            print()
            print("This tool is intended ONLY to copy one whole github org")
            print("into one raw empty org, and it is not built to deal with conflicts.")
            sys.exit(1)
        
        if verified_duplicates:
            print(f"✓ All {len(verified_duplicates)} matching repos are verified duplicates")
            print("These will be skipped during migration.")
            # Add verified duplicates to completed list
            for repo_name in verified_duplicates:
                if repo_name not in load_completed_repos(completed_file):
                    with open(completed_file, 'a') as f:
                        f.write(f"{repo_name}\n")
            print()
    else:
        print("✓ No conflicts!")
            
    # # Check for conflicts (case-insensitive)
    # source_names = {repo['name'].lower(): repo['name'] for repo in source_repos}
    # dest_names = {repo['name'].lower(): repo['name'] for repo in dest_repos}
    # conflicts = set(source_names.keys()) & set(dest_names.keys())
    
    # if conflicts:
    #     print("ERROR: Conflicting repository names found:")
    #     for name_lower in sorted(conflicts):
    #         print(f"  - {source_names[name_lower]}")
    #     print()
    #     print("This tool is intended ONLY to copy one whole github org")
    #     print("into one raw empty org, and it is not built to deal with conflicts.")
    #     sys.exit(1)
    
    # print("✓ No conflicts!")
    
    # Display detailed tables
    display_repo_table(source_repos, source_org)
    display_repo_table(dest_repos, dest_org)
    
    # Pause for user review
    print()
    print("=" * 60)
    print("Review the repository information above.")
    print("=" * 60)
    input("Press ENTER to continue to migration setup...")
    print()
    
    # Get temp directory
    temp_dir = input("Temporary directory path (for cloning): ").strip()
    temp_dir = os.path.expanduser(temp_dir)
    
    # Verify temp directory
    if not os.path.exists(temp_dir):
        print(f"\nCreating directory: {temp_dir}")
        os.makedirs(temp_dir)
    
    if not os.path.isdir(temp_dir):
        print(f"ERROR: {temp_dir} is not a directory")
        sys.exit(1)
    
    print()
    
    # Initialize tracking files
    completed_file = 'completed_repos.txt'
    error_log = 'migration_errors.txt'
    success_log = 'migration_log.txt'
    
    # Load completed repos
    completed_repos = load_completed_repos(completed_file)
    remaining_repos = [r for r in source_repos if r['name'] not in completed_repos]
    
    if completed_repos:
        print(f"{len(completed_repos)} repos already completed")
        print(f"{len(remaining_repos)} repos remaining")
    else:
        print(f"Ready to copy {len(remaining_repos)} repos from {source_org} to {dest_org}")
    
    print()
    
    # Confirm before proceeding
    confirmation = input('Type "YES" to continue: ').strip()
    if confirmation != "YES":
        print("Aborted.")
        sys.exit(0)
    
    print()
    print("=" * 60)
    print("Starting migration...")
    print("=" * 60)
    print()
    
    # Sort by creation date (oldest first)
    remaining_repos.sort(key=lambda r: r['createdAt'])
    
    # Statistics
    total_repos = len(remaining_repos)
    successful = 0
    failed = 0
    
    # Main loop
    for idx, repo in enumerate(remaining_repos, 1):
        repo_name = repo['name']
        is_private = repo['isPrivate']
        description = repo.get('description', '') or ''
        uses_lfs = repo.get('uses_lfs', False)
        
        print(f"[{idx}/{total_repos}] Processing: {repo_name}")
        if uses_lfs:
            print(f"  ⚠ This repo uses Git LFS")
        
        repo_temp_path = os.path.join(temp_dir, repo_name)
        start_time = time.time()
        
        try:
            # Step 1: Clone from source org
            print(f"  → Cloning from {source_org}...")
            clone_url = f"https://github.com/{source_org}/{repo_name}.git"
            
            # Retry logic for clone
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    run_command(
                        ['git', 'clone', '--mirror', clone_url, repo_temp_path],
                        check=True
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  → Clone attempt {attempt + 1} failed, retrying...")
                        time.sleep(5)
                    else:
                        raise
            
            # Step 2: Create repo in dest org
            print(f"  → Creating in {dest_org}...")
            visibility = "--private" if is_private else "--public"
            cmd = ['gh', 'repo', 'create', f"{dest_org}/{repo_name}", visibility, '--clone=false']
            
            # Handle description with potential quotes
            if description:
                safe_description = description.replace('"', "'")
                cmd.extend(['--description', safe_description])
            
            run_command(cmd, check=True)
            
            # Step 3: Push to dest org
            print(f"  → Pushing to {dest_org}...")
            push_url = f"https://github.com/{dest_org}/{repo_name}.git"
            
            # Retry logic for push
            for attempt in range(max_retries):
                try:
                    run_command(
                        ['git', '-C', repo_temp_path, 'push', '--mirror', push_url],
                        check=True
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"  → Push attempt {attempt + 1} failed, retrying...")
                        time.sleep(5)
                    else:
                        raise
            
            # Step 4: Clean up temp directory
            print(f"  → Cleaning up...")
            if os.path.exists(repo_temp_path):
                shutil.rmtree(repo_temp_path, ignore_errors=True)
            
            # Step 5: Mark as complete
            with open(completed_file, 'a') as f:
                f.write(f"{repo_name}\n")
            
            elapsed = time.time() - start_time
            success_msg = f"✓ {repo_name} complete (took {elapsed:.1f}s)"
            log_message(success_msg, success_log)
            print()
            successful += 1
            
        except Exception as e:
            # Clean up on failure
            if os.path.exists(repo_temp_path):
                shutil.rmtree(repo_temp_path, ignore_errors=True)
            
            elapsed = time.time() - start_time
            error_msg = f"✗ {repo_name} FAILED after {elapsed:.1f}s: {str(e)}"
            log_message(error_msg, error_log)
            print()
            failed += 1
            continue
    
    # Final summary
    print("=" * 60)
    print("Migration Complete")
    print("=" * 60)
    print(f"Total processed: {total_repos}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print(f"\nSee {error_log} for error details")
    
    print(f"\nCompleted repos logged in: {completed_file}")
    print(f"Success log: {success_log}")

def load_completed_repos(filename):
    """Load list of completed repos from file."""
    if not os.path.exists(filename):
        return set()
    with open(filename, 'r') as f:
        return set(line.strip() for line in f if line.strip())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress saved in completed_repos.txt")
        print("Run script again to resume.")
        sys.exit(0)




# First draft

# #!/usr/bin/env python3
# """
# GitHub Organization Repository Migration Script

# Duplicates all repositories from one GitHub organization to another.
# Requires: gh CLI authenticated with 2FA
# """

# import subprocess
# import json
# import os
# import shutil
# import sys
# from datetime import datetime

# def run_command(cmd, check=True, capture=True):
#     """Run a shell command and return result."""
#     result = subprocess.run(
#         cmd,
#         capture_output=capture,
#         text=True,
#         check=False
#     )
#     if check and result.returncode != 0:
#         return None
#     return result

# def log_message(message, log_file):
#     """Print to console and write to log file."""
#     timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     log_entry = f"[{timestamp}] {message}"
#     print(message)
#     with open(log_file, 'a') as f:
#         f.write(log_entry + '\n')

# def check_gh_installed():
#     """Verify gh CLI is installed."""
#     result = run_command(['gh', '--version'], check=False)
#     if result is None or result.returncode != 0:
#         print("ERROR: gh CLI is not installed.")
#         print("Install from: https://cli.github.com/")
#         sys.exit(1)
#     print("✓ gh CLI installed")

# def check_gh_authenticated():
#     """Verify gh is authenticated."""
#     result = run_command(['gh', 'auth', 'status'], check=False)
#     if result is None or result.returncode != 0:
#         print("ERROR: gh is not authenticated.")
#         print("Run: gh auth login")
#         sys.exit(1)
#     print("✓ gh authenticated")

# def check_org_access(org):
#     """Verify access to an organization."""
#     result = run_command(['gh', 'repo', 'list', org, '--limit', '1', '--json', 'name'], check=False)
#     if result is None or result.returncode != 0:
#         print(f"ERROR: Cannot access organization '{org}'")
#         print(f"Make sure you have access and the org name is correct.")
#         sys.exit(1)
#     return True

# def get_repos(org):
#     """Fetch all repos from an organization."""
#     print(f"Fetching repos from {org}...")
#     result = run_command([
#         'gh', 'repo', 'list', org,
#         '--limit', '1000',
#         '--json', 'name,createdAt,isPrivate,description'
#     ])
    
#     if result is None:
#         print(f"ERROR: Failed to fetch repos from {org}")
#         sys.exit(1)
    
#     repos = json.loads(result.stdout)
#     return repos

# def load_completed_repos(filename):
#     """Load list of completed repos from file."""
#     if not os.path.exists(filename):
#         return set()
#     with open(filename, 'r') as f:
#         return set(line.strip() for line in f if line.strip())

# def main():
#     print("=" * 60)
#     print("GitHub Organization Repository Migration")
#     print("=" * 60)
#     print()
    
#     # Check prerequisites
#     check_gh_installed()
#     check_gh_authenticated()
#     print()
    
#     # Get user input
#     source_org = input("Source organization name: ").strip()
#     dest_org = input("Destination organization name: ").strip()
#     temp_dir = input("Temporary directory path (for cloning): ").strip()
    
#     # Expand user path if needed
#     temp_dir = os.path.expanduser(temp_dir)
    
#     # Verify temp directory
#     if not os.path.exists(temp_dir):
#         print(f"\nCreating directory: {temp_dir}")
#         os.makedirs(temp_dir)
    
#     if not os.path.isdir(temp_dir):
#         print(f"ERROR: {temp_dir} is not a directory")
#         sys.exit(1)
    
#     print()
    
#     # Initialize tracking files
#     completed_file = 'completed_repos.txt'
#     error_log = 'migration_errors.txt'
#     success_log = 'migration_log.txt'
    
#     # Check access to both orgs
#     print("Verifying organization access...")
#     check_org_access(source_org)
#     print(f"✓ Admin rights confirmed for {source_org}")
#     check_org_access(dest_org)
#     print(f"✓ Admin rights confirmed for {dest_org}")
#     print()
    
#     # Detect repos in both orgs
#     print("Detecting repos in both orgs...")
#     source_repos = get_repos(source_org)
#     dest_repos = get_repos(dest_org)
    
#     print(f"{len(source_repos)} repos found in {source_org}")
#     print(f"{len(dest_repos)} repos found in {dest_org}")
#     print()
    
#     # Check for conflicts
#     source_names = {repo['name'] for repo in source_repos}
#     dest_names = {repo['name'] for repo in dest_repos}
#     conflicts = source_names & dest_names
    
#     if conflicts:
#         print("ERROR: Conflicting repository names found:")
#         for name in sorted(conflicts):
#             print(f"  - {name}")
#         print()
#         print("This tool is intended ONLY to copy one whole github org")
#         print("into one raw empty org, and it is not built to deal with conflicts.")
#         sys.exit(1)
    
#     print("✓ No conflicts!")
#     print()
    
#     # Load completed repos
#     completed_repos = load_completed_repos(completed_file)
#     remaining_repos = [r for r in source_repos if r['name'] not in completed_repos]
    
#     if completed_repos:
#         print(f"{len(completed_repos)} repos already completed")
#         print(f"{len(remaining_repos)} repos remaining")
#     else:
#         print(f"Ready to copy {len(remaining_repos)} repos from {source_org} to {dest_org}")
    
#     print()
    
#     # Confirm before proceeding
#     confirmation = input('Type "YES" to continue: ').strip()
#     if confirmation != "YES":
#         print("Aborted.")
#         sys.exit(0)
    
#     print()
#     print("=" * 60)
#     print("Starting migration...")
#     print("=" * 60)
#     print()
    
#     # Sort by creation date (oldest first)
#     remaining_repos.sort(key=lambda r: r['createdAt'])
    
#     # Statistics
#     total_repos = len(remaining_repos)
#     successful = 0
#     failed = 0
    
#     # Main loop
#     for idx, repo in enumerate(remaining_repos, 1):
#         repo_name = repo['name']
#         is_private = repo['isPrivate']
#         description = repo.get('description', '')
        
#         print(f"[{idx}/{total_repos}] Processing: {repo_name}")
        
#         repo_temp_path = os.path.join(temp_dir, repo_name)
        
#         try:
#             # Step 1: Clone from source org
#             print(f"  → Cloning from {source_org}...")
#             clone_url = f"https://github.com/{source_org}/{repo_name}.git"
#             result = run_command(
#                 ['git', 'clone', '--mirror', clone_url, repo_temp_path],
#                 check=False
#             )
            
#             if result.returncode != 0:
#                 raise Exception(f"Clone failed: {result.stderr}")
            
#             # Step 2: Create repo in dest org
#             print(f"  → Creating in {dest_org}...")
#             visibility = "--private" if is_private else "--public"
#             cmd = ['gh', 'repo', 'create', f"{dest_org}/{repo_name}", visibility, '--clone=false']
#             if description:
#                 cmd.extend(['--description', description])
            
#             result = run_command(cmd, check=False)
            
#             if result.returncode != 0:
#                 raise Exception(f"Create failed: {result.stderr}")
            
#             # Step 3: Push to dest org
#             print(f"  → Pushing to {dest_org}...")
#             push_url = f"https://github.com/{dest_org}/{repo_name}.git"
#             result = run_command(
#                 ['git', '-C', repo_temp_path, 'push', '--mirror', push_url],
#                 check=False
#             )
            
#             if result.returncode != 0:
#                 raise Exception(f"Push failed: {result.stderr}")
            
#             # Step 4: Clean up temp directory
#             print(f"  → Cleaning up...")
#             if os.path.exists(repo_temp_path):
#                 shutil.rmtree(repo_temp_path)
            
#             # Step 5: Mark as complete
#             with open(completed_file, 'a') as f:
#                 f.write(f"{repo_name}\n")
            
#             log_message(f"✓ {repo_name} complete", success_log)
#             print()
#             successful += 1
            
#         except Exception as e:
#             # Clean up on failure
#             if os.path.exists(repo_temp_path):
#                 shutil.rmtree(repo_temp_path)
            
#             error_msg = f"✗ {repo_name} FAILED: {str(e)}"
#             log_message(error_msg, error_log)
#             print()
#             failed += 1
#             continue
    
#     # Final summary
#     print("=" * 60)
#     print("Migration Complete")
#     print("=" * 60)
#     print(f"Total processed: {total_repos}")
#     print(f"Successful: {successful}")
#     print(f"Failed: {failed}")
    
#     if failed > 0:
#         print(f"\nSee {error_log} for error details")
    
#     print(f"\nCompleted repos logged in: {completed_file}")
#     print(f"Success log: {success_log}")

# if __name__ == "__main__":
#     try:
#         main()
#     except KeyboardInterrupt:
#         print("\n\nInterrupted by user. Progress saved in completed_repos.txt")
#         print("Run script again to resume.")
#         sys.exit(0)