# 1. Verify gh is installed and authenticated
gh --version
gh auth status

# 2. Verify git is installed
git --version

# 3. Tell git to use gh credentials (IMPORTANT)
gh auth setup-git

# 4. Test access to both orgs
gh repo list True-Bots --limit 1
gh repo list True-Bots-Inc --limit 1

# 5. Check disk space in your temp directory
# Make sure you have at least a few GB free