import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

class GitHubContributionsAnalyzer:
    def __init__(self, github_token, org_name):
        """
        Initialize the GitHub Contributions Analyzer
        
        :param github_token: GitHub Personal Access Token
        :param org_name: GitHub Organization name
        """
        self.github_token = github_token
        self.org_name = org_name
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }

    def get_organization_repos(self):
        """
        Retrieve all repositories for the specified organization
        
        :return: List of repository names
        """
        repos_url = f'https://api.github.com/orgs/{self.org_name}/repos'
        response = requests.get(repos_url, headers=self.headers)
        response.raise_for_status()
        return [repo['full_name'] for repo in response.json()]

    def get_repository_contributors(self, repo_full_name):
        """
        Retrieve contributors for a specific repository
        
        :param repo_full_name: Full repository name (owner/repo)
        :return: List of contributor usernames
        """
        contributors_url = f'https://api.github.com/repos/{repo_full_name}/contributors'
        response = requests.get(contributors_url, headers=self.headers)
        response.raise_for_status()
        return [contributor['login'] for contributor in response.json()]

    def get_contributor_contributions(self, repo_full_name, contributor, start_date, end_date):
        """
        Retrieve contribution data for a specific contributor and repository
        
        :param repo_full_name: Full repository name (owner/repo)
        :param contributor: GitHub username
        :param start_date: Start date for contribution analysis
        :param end_date: End date for contribution analysis
        :return: DataFrame of contributions
        """
        # GitHub search API for commits
        search_url = 'https://api.github.com/search/commits'
        params = {
            'q': f'repo:{repo_full_name} author:{contributor} committer-date:{start_date}..{end_date}',
            'sort': 'committer-date',
            'order': 'desc'
        }
        
        response = requests.get(search_url, headers=self.headers, params=params)
        response.raise_for_status()
        
        commits = response.json().get('items', [])
        
        # Convert commits to DataFrame
        df = pd.DataFrame([
            {
                'repository': repo_full_name,
                'contributor': contributor,
                'commit_date': datetime.strptime(commit['commit']['committer']['date'], '%Y-%m-%dT%H:%M:%SZ').date(),
                'additions': commit['stats']['additions'] if 'stats' in commit else 0,
                'deletions': commit['stats']['deletions'] if 'stats' in commit else 0
            } 
            for commit in commits
        ])
        
        return df

    def analyze_contributions(self, start_date=None, end_date=None):
        """
        Analyze contributions across all repositories and contributors
        
        :param start_date: Start date for analysis (defaults to 1 year ago)
        :param end_date: End date for analysis (defaults to today)
        :return: Dictionary of contribution analyses
        """
        # Set default dates if not provided
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)
        if not end_date:
            end_date = datetime.now()
        
        # Convert dates to string format GitHub API expects
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # Get repositories and contributors
        repos = self.get_organization_repos()
        
        # Collect all contributions
        all_contributions = []
        
        for repo in repos:
            contributors = self.get_repository_contributors(repo)
            
            for contributor in contributors:
                try:
                    contrib_df = self.get_contributor_contributions(repo, contributor, start_date_str, end_date_str)
                    all_contributions.append(contrib_df)
                except Exception as e:
                    print(f"Error retrieving contributions for {contributor} in {repo}: {e}")
        
        # Combine all contributions
        if not all_contributions:
            print("No contributions found.")
            return {}
        
        contributions_df = pd.concat(all_contributions, ignore_index=True)
        
        # Aggregate analyses
        analyses = {
            'daily_contributions': contributions_df.groupby(['repository', 'contributor', 'commit_date']).agg({
                'additions': 'sum',
                'deletions': 'sum'
            }).reset_index(),
            
            'weekly_contributions': contributions_df.groupby([
                'repository', 
                'contributor', 
                pd.Grouper(key='commit_date', freq='W')
            ]).agg({
                'additions': 'sum',
                'deletions': 'sum'
            }).reset_index(),
            
            'monthly_contributions': contributions_df.groupby([
                'repository', 
                'contributor', 
                pd.Grouper(key='commit_date', freq='M')
            ]).agg({
                'additions': 'sum',
                'deletions': 'sum'
            }).reset_index()
        }
        
        return analyses

    def export_reports(self, analyses, output_dir='github_contributions_reports'):
        """
        Export contribution analyses to CSV files
        
        :param analyses: Dictionary of contribution analyses
        :param output_dir: Directory to save report files
        """
        os.makedirs(output_dir, exist_ok=True)
        
        for granularity, df in analyses.items():
            filename = os.path.join(output_dir, f'{granularity}_report.csv')
            df.to_csv(filename, index=False)
            print(f"Exported {granularity} report to {filename}")

def main():
    # Pull GitHub token and organization name from environment variables
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
    ORGANIZATION_NAME = os.environ.get('ORGANIZATION_NAME')
    
    # Validate required environment variables
    if not GITHUB_TOKEN or not ORGANIZATION_NAME:
        raise ValueError("GITHUB_TOKEN and ORGANIZATION_NAME must be set as environment variables")
    
    # Optional: specify custom date range
    start_date = datetime.now() - timedelta(days=365)  # One year ago
    end_date = datetime.now()
    
    # Initialize and run analysis
    analyzer = GitHubContributionsAnalyzer(GITHUB_TOKEN, ORGANIZATION_NAME)
    
    try:
        contributions_analyses = analyzer.analyze_contributions(start_date, end_date)
        analyzer.export_reports(contributions_analyses)
        print("Contribution analysis completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    main()