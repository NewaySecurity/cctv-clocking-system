# GitHub Setup Instructions for NEWAY SECURITY CCTV CLOCKING SYSTEM

This document provides step-by-step instructions for setting up a GitHub repository for the NEWAY SECURITY CCTV CLOCKING SYSTEM and pushing the code to it.

## Prerequisites

- Git installed on your computer (already done)
- GitHub account (you'll need to create one if you don't have it)
- Basic familiarity with Git commands

## Step 1: Create a GitHub Account

If you don't already have a GitHub account:

1. Visit [GitHub](https://github.com)
2. Click "Sign up" and follow the registration process
3. Verify your email address when prompted

## Step 2: Create a New Repository on GitHub

1. Log in to your GitHub account
2. Click the "+" icon in the top right corner and select "New repository"
3. Set repository name: `cctv-clocking-system`
4. Set repository owner: Select the organization `NewaySecurity` if it exists, or your personal account
5. Add a description: "NEWAY SECURITY CCTV CLOCKING SYSTEM - Face recognition attendance system using RTSP camera feeds"
6. Set visibility: Choose either "Public" or "Private" based on your requirements
7. **DO NOT** initialize the repository with a README, .gitignore, or license as we already have these files
8. Click "Create repository"

## Step 3: Create the GitHub Organization (Optional)

If the `NewaySecurity` organization doesn't exist yet and you want to create it:

1. Click your profile picture in the top right corner
2. Click "Your organizations"
3. Click "New organization"
4. Select the free plan
5. Enter organization name: "NewaySecurity"
6. Enter contact email
7. Follow the remaining prompts to complete the setup

## Step 4: Push Existing Code to GitHub

After creating the repository, GitHub will show instructions for pushing an existing repository. From your local repository directory, run the following commands:

```bash
# The remote has already been added with:
# git remote add origin https://github.com/NewaySecurity/cctv-clocking-system.git

# Push your code to GitHub
git push -u origin master
```

If you're prompted for credentials:
- Username: Your GitHub username
- Password: Use a personal access token (PAT) instead of your password

## Step 5: Create a Personal Access Token (if needed)

If you need to create a Personal Access Token for authentication:

1. On GitHub, click your profile photo in the top right
2. Go to Settings → Developer settings → Personal access tokens → Tokens (classic)
3. Click "Generate new token" → "Generate new token (classic)"
4. Give your token a descriptive name
5. Select scopes: at minimum check "repo" for full repository access
6. Click "Generate token"
7. **IMPORTANT**: Copy the token immediately and store it securely. You won't be able to see it again!

## Step 6: Alternative Authentication Methods

If you prefer not to use PAT authentication in the terminal:

### Option 1: GitHub CLI
1. Install GitHub CLI from https://cli.github.com/
2. Run `gh auth login` and follow prompts
3. Then push with `gh repo push`

### Option 2: SSH Authentication
1. [Generate an SSH key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
2. [Add the key to your GitHub account](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)
3. Change the remote URL to SSH: `git remote set-url origin git@github.com:NewaySecurity/cctv-clocking-system.git`
4. Push with `git push -u origin master`

## Step 7: Verify Repository Setup

After pushing your code:

1. Refresh your GitHub repository page
2. Verify that all files appear correctly
3. Check that the README.md displays properly on the repository's main page

## Step 8: Set Up Branch Protection (Recommended)

To protect your main branch:

1. Go to your repository on GitHub
2. Click Settings → Branches
3. Under "Branch protection rules", click "Add rule"
4. In "Branch name pattern", enter "master" or "main" (depending on your default branch)
5. Select appropriate protection options like:
   - Require pull request reviews before merging
   - Require status checks to pass before merging
   - Include administrators
6. Click "Create" or "Save changes"

## Step 9: Set Up GitHub Pages for Documentation (Optional)

If you want to create a documentation website:

1. Go to your repository settings
2. Scroll down to "Pages"
3. Set Source to "Deploy from a branch"
4. Select the branch (usually "master" or "main") and folder (usually "/docs")
5. Click "Save"
6. Your documentation will be available at: https://newaysecurity.github.io/cctv-clocking-system/

## Troubleshooting

### Push Errors
- **Authentication failed**: Make sure you're using the correct username and a valid personal access token, not your password
- **Repository not found**: Verify the repository URL and your permissions
- **Rejected non-fast-forward updates**: Try pulling first with `git pull --rebase origin master`

### Other Issues
- If you encounter other issues, consult the [GitHub documentation](https://docs.github.com/en) or reach out to GitHub support

## Conclusion

Your NEWAY SECURITY CCTV CLOCKING SYSTEM code should now be properly stored and version-controlled on GitHub. Team members can clone the repository to work on the code, submit pull requests for changes, and collaborate effectively on the project.

