

docker build -t github-contributions-analyzer .

docker run -e GITHUB_TOKEN=$GITHUB_TOKEN \
           -e ORGANIZATION_NAME=$ORG \
           -v $(pwd)/github_contributions_reports:/app/github_contributions_reports \
           github-contributions-analyzer