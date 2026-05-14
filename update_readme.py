#!/usr/bin/env python3
import requests
import re
from os import environ

GITHUB_USERNAME = "bayumutawakkil"
README_FILE = "README.md"

def fetch_repositories():
    """Fetch repositories and get contribution count for each"""
    token = environ.get('GITHUB_TOKEN', '')
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    # Fetch user repositories
    repos_url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
    params = {"sort": "updated", "per_page": 100}
    
    print(f"Fetching repositories for {GITHUB_USERNAME}...")
    repos_response = requests.get(repos_url, headers=headers, params=params)
    repos_response.raise_for_status()
    repos = repos_response.json()
    
    # Filter out forks
    own_repos = [r for r in repos if not r['fork']]
    
    # Get contribution count for each
    repos_with_contributions = []
    
    for repo in own_repos:
        try:
            contributors_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo['name']}/contributors"
            contrib_response = requests.get(contributors_url, headers=headers, params={"per_page": 100})
            
            if contrib_response.status_code == 200:
                contributors = contrib_response.json()
                user_contrib = next(
                    (c['contributions'] for c in contributors if c['login'].lower() == GITHUB_USERNAME.lower()),
                    0
                )
            else:
                user_contrib = 0
            
            repos_with_contributions.append({
                "name": repo['name'],
                "description": repo['description'] or "No description",
                "url": repo['html_url'],
                "contributions": user_contrib
            })
            
            print(f"  {repo['name']}: {user_contrib} commits")
        except Exception as e:
            print(f"  Error fetching {repo['name']}: {e}")
    
    # Sort by contributions and get top 3
    top_repos = sorted(repos_with_contributions, key=lambda x: x['contributions'], reverse=True)[:3]
    
    return top_repos

def generate_project_rows(repos):
    """Generate markdown table rows for projects"""
    return "\n".join([
        f"| {r['name']} | {r['description']} | [View]({r['url']}) |"
        for r in repos
    ])

def update_readme(repos):
    """Update README with top repositories"""
    with open(README_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    project_rows = generate_project_rows(repos)
    
    # Replace the Featured Projects section
    pattern = r'## Featured Projects\n\n\| Project \| Description \| Link \|\n\|------\|----------\|------\|\n(.*?)\n\n---'
    
    new_section = f"""## Featured Projects

| Project | Description | Link |
|---------|-------------|------|
{project_rows}

---"""
    
    updated_content = re.sub(pattern, new_section, content, flags=re.DOTALL)
    
    with open(README_FILE, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"\n✅ README.md updated successfully!")
    print("\nTop 3 repositories by your contributions:")
    for i, repo in enumerate(repos, 1):
        print(f"{i}. {repo['name']} ({repo['contributions']} commits)")

if __name__ == "__main__":
    try:
        repos = fetch_repositories()
        if repos:
            update_readme(repos)
        else:
            print("No repositories found")
    except Exception as e:
        print(f"Error: {e}")
