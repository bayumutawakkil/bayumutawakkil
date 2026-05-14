const fs = require('fs');
const https = require('https');

const GITHUB_USERNAME = 'bayumutawakkil';
const README_FILE = 'README.md';

// Helper function to make HTTPS requests
function makeRequest(hostname, path) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: hostname,
      path: path,
      method: 'GET',
      headers: {
        'User-Agent': 'Node.js',
        'Authorization': `token ${process.env.GITHUB_TOKEN}`
      }
    };

    https.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (error) {
          reject(error);
        }
      });
    }).on('error', reject);
  });
}

// Get contribution count for user in a specific repo
async function getContributionCount(repo) {
  try {
    const contributors = await makeRequest(
      'api.github.com',
      `/repos/${GITHUB_USERNAME}/${repo.name}/contributors?per_page=100`
    );

    // Find this user's contribution count
    const userContribution = contributors.find(
      c => c.login.toLowerCase() === GITHUB_USERNAME.toLowerCase()
    );

    return userContribution ? userContribution.contributions : 0;
  } catch (error) {
    console.log(`Could not fetch contributors for ${repo.name}`);
    return 0;
  }
}

// Fetch repositories from GitHub API
async function fetchRepositories() {
  try {
    const repos = await makeRequest(
      'api.github.com',
      `/users/${GITHUB_USERNAME}/repos?sort=updated&order=desc&per_page=100`
    );

    // Filter out forks
    const ownRepos = repos.filter(repo => !repo.fork);

    // Get contribution count for each repo
    const reposWithContributions = await Promise.all(
      ownRepos.map(async (repo) => {
        const contributions = await getContributionCount(repo);
        return {
          ...repo,
          contributionCount: contributions
        };
      })
    );

    // Sort by contribution count and get top 3
    const topRepos = reposWithContributions
      .sort((a, b) => b.contributionCount - a.contributionCount)
      .slice(0, 3);

    return topRepos;
  } catch (error) {
    throw error;
  }
}

// Generate project table rows
function generateProjectRows(repos) {
  return repos
    .map(repo => 
      `| ${repo.name} | ${repo.description || 'No description'} | [View](${repo.html_url}) |`
    )
    .join('\n');
}

// Update README with new projects
function updateReadme(repos) {
  let content = fs.readFileSync(README_FILE, 'utf8');

  const projectRows = generateProjectRows(repos);
  
  // Find and replace the Featured Projects section
  const projectPattern = /## Featured Projects\n\n\| Project \| Description \| Link \|\n\|------\|----------\|------\|\n(.*?)\n\n---/s;
  
  const newProjectsSection = `## Featured Projects

| Project | Description | Link |
|---------|-------------|------|
${projectRows}

---`;

  if (projectPattern.test(content)) {
    content = content.replace(projectPattern, newProjectsSection);
  } else {
    console.error('Could not find Featured Projects section in README.md');
    process.exit(1);
  }

  fs.writeFileSync(README_FILE, content, 'utf8');
  console.log('README.md updated successfully with top 3 repositories');
}

// Main execution
async function main() {
  try {
    console.log(`Fetching repositories and contribution data for ${GITHUB_USERNAME}...`);
    const repos = await fetchRepositories();
    
    if (repos.length === 0) {
      console.log('No repositories found or all are forks');
      process.exit(0);
    }

    console.log(`Found top repositories by contributions`);
    console.log('Top 3 repositories by your contributions:');
    repos.forEach((repo, index) => {
      console.log(`${index + 1}. ${repo.name} (${repo.contributionCount} commits)`);
    });

    updateReadme(repos);
    console.log('Update completed!');
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

main();
