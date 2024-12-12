import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def parse_datetime(self, timestamp_str):
        """
        Flexible datetime parsing to handle multiple timestamp formats
        
        :param timestamp_str: Timestamp string to parse
        :return: Parsed datetime object
        """
        timestamp_formats = [
            '%Y-%m-%dT%H:%M:%SZ',  # Original GitHub format
            '%Y-%m-%dT%H:%M:%S.%f%z',  # Format with microseconds and timezone
            '%Y-%m-%dT%H:%M:%S%z'  # Format with timezone
        ]
        
        for fmt in timestamp_formats:
            try:
                return datetime.strptime(timestamp_str, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse timestamp: {timestamp_str}")

    def get_organization_repos(self):
        """
        Retrieve all repositories for the specified organization
        
        :return: List of repository names
        """
        repos_url = f'https://api.github.com/orgs/{self.org_name}/repos'
        response = self.session.get(repos_url)
        
        # Handle potential rate limiting
        if response.status_code == 403:
            logger.warning("Rate limit encountered. Waiting before retrying.")
            time.sleep(60)  # Wait for 1 minute
            response = self.session.get(repos_url)
        
        response.raise_for_status()
        return [repo['full_name'] for repo in response.json()]

    def get_repository_contributors(self, repo_full_name):
        """
        Retrieve contributors for a specific repository
        
        :param repo_full_name: Full repository name (owner/repo)
        :return: List of contributor usernames
        """
        contributors_url = f'https://api.github.com/repos/{repo_full_name}/contributors'
        response = self.session.get(contributors_url)
        
        # Handle potential rate limiting
        if response.status_code == 403:
            logger.warning("Rate limit encountered. Waiting before retrying.")
            time.sleep(60)  # Wait for 1 minute
            response = self.session.get(contributors_url)
        
        response.raise_for_status()
        return [contributor['login'] for contributor in response.json()]

    def fetch_commits_for_contributor(self, repo_full_name, contributor, start_date, end_date):
        """
        Fetch commits for a specific contributor in a repository
        
        :param repo_full_name: Full repository name
        :param contributor: GitHub username
        :param start_date: Start date for contributions
        :param end_date: End date for contributions
        :return: List of commits
        """
        commits_url = f'https://api.github.com/repos/{repo_full_name}/commits'
        
        params = {
            'author': contributor,
            'since': start_date.isoformat() + 'T00:00:00Z',
            'until': end_date.isoformat() + 'T23:59:59Z',
            'per_page': 100
        }
        
        all_commits = []
        page = 1
        
        while True:
            params['page'] = page
            try:
                response = self.session.get(commits_url, params=params)
                
                # Handle rate limiting
                if response.status_code == 403:
                    logger.warning("Rate limit encountered. Waiting before retrying.")
                    time.sleep(60)  # Wait for 1 minute
                    response = self.session.get(commits_url, params=params)
                
                response.raise_for_status()
                page_commits = response.json()
                
                if not page_commits:
                    break
                
                all_commits.extend(page_commits)
                page += 1
                
                # Prevent infinite loops or excessive API calls
                if page > 10:  # Limit to first 1000 commits
                    break
                
            except Exception as e:
                logger.error(f"Error fetching commits for {contributor} in {repo_full_name}: {e}")
                break
        
        return all_commits

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
        
        # Get repositories
        repos = self.get_organization_repos()
        
        # Collect all contributions
        all_contributions = []
        
        for repo in repos:
            try:
                # Get contributors for this repository
                contributors = self.get_repository_contributors(repo)
                
                for contributor in contributors:
                    try:
                        # Fetch commits
                        commits = self.fetch_commits_for_contributor(repo, contributor, start_date, end_date)
                        
                        # Process commits
                        commits_data = [
                            {
                                'repository': repo,
                                'contributor': contributor,
                                'commit_date': self.parse_datetime(commit['commit']['committer']['date']),
                                'commit_count': 1
                            } 
                            for commit in commits
                        ]
                        
                        if commits_data:
                            all_contributions.extend(commits_data)
                    
                    except Exception as e:
                        logger.error(f"Error processing contributions for {contributor} in {repo}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing repository {repo}: {e}")
        
        # Create DataFrame
        if not all_contributions:
            logger.warning("No contributions found.")
            return {}
        
        contributions_df = pd.DataFrame(all_contributions)
        
        # Ensure commit_date is datetime
        contributions_df['commit_date'] = pd.to_datetime(contributions_df['commit_date'])
        
        # Aggregate analyses
        analyses = {
            'daily_contributions': contributions_df.groupby([
                'repository', 
                'contributor', 
                pd.Grouper(key='commit_date', freq='D')
            ])['commit_count'].sum().reset_index(),
            
            'weekly_contributions': contributions_df.groupby([
                'repository', 
                'contributor', 
                pd.Grouper(key='commit_date', freq='W')
            ])['commit_count'].sum().reset_index(),
            
            'monthly_contributions': contributions_df.groupby([
                'repository', 
                'contributor', 
                pd.Grouper(key='commit_date', freq='M')
            ])['commit_count'].sum().reset_index()
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
            logger.info(f"Exported {granularity} report to {filename}")

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
        logger.info("Contribution analysis completed successfully.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    main()