# GitHub Organization Duplicator

A Python script to duplicate all repositories from one GitHub organization to another, preserving all branches, tags, commit history, and repository metadata.

## Purpose

This tool is designed for **one-time complete organization migrations** where you need to copy an entire GitHub organization's repositories into a new, empty organization. It is **not** designed to handle conflicts or merge with existing repositories.

## Features

- ✅ Duplicates all repositories with complete git history
- ✅ Preserves all branches and tags
- ✅ Maintains repository privacy settings (public/private)
- ✅ Preserves repository descriptions
- ✅ Detects Git LFS usage and warns about special handling requirements
- ✅ Resumable - if interrupted, rerun to continue from where it stopped
- ✅ Retry logic for network issues (3 attempts per operation)
- ✅ Detailed logging and progress tracking
- ✅ Shows timing information for each repository

## Prerequisites

### Required Software

1. **Python 3.7+**
   - Check: `python --version`

2. **GitHub CLI (`gh`)**
   - Install on Windows: `winget install --id GitHub.cli`
   - Install on macOS: `brew install gh`
   - Install on Linux: See https://cli.github.com/
   - Check: `gh --version`

3. **Git**
   - Install: https://git-scm.com/downloads
   - Check: `git --version`

### Authentication Setup

Before running the script, authenticate with GitHub:
```bash
# Authenticate with GitHub (includes 2FA)
gh auth login

# Configure git to use gh credentials
gh auth setup-git

# Verify authentication
gh auth status
```

### Permissions Required

- **Source organization**: Admin/Owner access (to read all repositories)
- **Destination organization**: Admin/Owner access (to create repositories)

## Pre-flight Checklist

Run these commands to verify everything is ready:
```bash
# 1. Verify gh is installed and authenticated
gh --version
gh auth status

# 2. Verify git is installed
git --version

# 3. Ensure git uses gh credentials
gh auth setup-git

# 4. Test access to both organizations
gh repo list SOURCE-ORG --limit 1
gh repo list DEST-ORG --limit 1

# 5. Check available disk space for temp directory
# Ensure you have at least 3-5 GB free
```

## Usage

1. **Run the script:**
```bash
   python git-org-duplicator.py
```

2. **Follow the prompts:**
   - Enter source organization name
   - Enter destination organization name
   - Review detailed repository tables (shows size, privacy, LFS status)
   - Press ENTER to continue
   - Specify temporary directory path (needs ~3-5 GB free space)
   - Type "YES" to confirm and start migration

3. **Monitor progress:**
   - The script will process repositories one at a time
   - Each repository shows: clone → create → push → cleanup
   - Timing information is displayed for each repository
   - Progress is logged to `migration_log.txt` and `migration_errors.txt`

## Output Files

The script creates three tracking files:

- **`completed_repos.txt`** - List of successfully migrated repositories (one per line)
- **`migration_log.txt`** - Timestamped log of successful migrations
- **`migration_errors.txt`** - Timestamped log of failed migrations with error details

## Resuming After Interruption

If the script is interrupted (Ctrl+C, network failure, etc.):

1. Simply **run the script again** with the same source/destination organizations
2. It will automatically skip repositories listed in `completed_repos.txt`
3. Failed repositories are **not** marked as complete, so they will be retried

## What Gets Migrated

### ✅ Included
- All git commit history
- All branches
- All tags
- All files and directories
- Repository name
- Repository description
- Privacy setting (public/private)
- Repository creation date (relative order preserved)

### ❌ Not Included
- GitHub Issues
- GitHub Pull Requests (PRs are not migrated, though PR refs may be copied)
- GitHub Actions secrets and workflows
- Repository settings (branch protection, webhooks, etc.)
- Collaborators and teams
- Stars, forks, and watchers counts
- GitHub Pages settings (pages content IS migrated if in a `gh-pages` branch)

## Git LFS Repositories

If repositories use Git LFS (Large File Storage):

1. The script will detect and warn you during the information gathering phase
2. LFS repositories may require manual handling after migration
3. Ensure you have Git LFS installed: `git lfs install`
4. You may need to manually configure LFS in the destination organization

## Limitations

- **Conflict handling**: Script will abort if destination org has any repositories with matching names
- **Repository size**: GitHub has a 2GB file size limit; larger files may cause push failures
- **API rate limits**: Unlikely but possible with very large organizations (>1000 repos)
- **Network reliability**: Large repositories may fail if network is unstable (retry logic helps)

## Troubleshooting

### "gh is not recognized"
- Install GitHub CLI: https://cli.github.com/
- Restart your terminal after installation

### "Authentication failed"
- Run: `gh auth login`
- Run: `gh auth setup-git`

### "Cannot access organization"
- Verify you have admin/owner access to both organizations
- Check organization name spelling (case-sensitive)

### Clone or push fails
- Check your internet connection
- Verify the repository isn't corrupted in the source org
- Check `migration_errors.txt` for specific error details
- Retry by running the script again (it will skip completed repos)

### Disk space errors
- Ensure temp directory has at least 3-5 GB free
- Largest repos may temporarily use significant space

## Example Run
```
============================================================
GitHub Organization Repository Migration
============================================================

✓ gh CLI installed
✓ gh authenticated
✓ git configured to use gh credentials

Source organization name: OldOrg
Destination organization name: NewOrg

Verifying organization access...
✓ Admin rights confirmed for OldOrg
✓ Admin rights confirmed for NewOrg

Detecting repos in both orgs...
✓ 51 repos found in OldOrg
✓ 0 repos found in NewOrg

✓ No conflicts!

[Detailed repository table displayed]

Press ENTER to continue to migration setup...
Temporary directory path: /tmp/migration

Ready to copy 51 repos from OldOrg to NewOrg
Type "YES" to continue: YES

============================================================
Starting migration...
============================================================

[1/51] Processing: first-repo
  → Cloning from OldOrg...
  → Creating in NewOrg...
  → Pushing to NewOrg...
  → Cleaning up...
✓ first-repo complete (took 12.3s)

[2/51] Processing: second-repo
...
```

## Technical Details

### Migration Process

For each repository, the script performs these steps:

1. **Clone**: `git clone --mirror` from source organization
2. **Create**: `gh repo create` in destination organization
3. **Push**: `git push --mirror` to destination repository
4. **Cleanup**: Remove temporary local clone
5. **Log**: Record success in `completed_repos.txt`

### Retry Logic

- Clone and push operations retry up to 3 times on failure
- 5-second delay between retry attempts
- Helps handle temporary network issues or rate limiting

### Sorting

Repositories are processed in order of creation date (oldest first) to preserve the relative chronological order in the destination organization.

## License

MIT License - Feel free to use and modify for your needs.

## Support

This is a one-time migration tool. For issues:
1. Check the `migration_errors.txt` file
2. Review GitHub CLI documentation: https://cli.github.com/manual/
3. Verify your GitHub organization permissions

## Notes

- This tool uses `git clone --mirror` and `git push --mirror` to ensure complete repository duplication
- Repositories are processed sequentially (one at a time) to avoid rate limiting
- The script is idempotent - safe to run multiple times
- No repositories are deleted from the source organization
- Temporary clones are automatically cleaned up after each repository
