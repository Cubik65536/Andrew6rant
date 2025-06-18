#!/usr/bin/env python3
"""
GitHub Language Analyzer with Terminal-Style SVG Generation

This script uses the GitHub GraphQL API to analyze the programming languages
used by a user based on their commit contributions across repositories.
Generates terminal-style SVG visualizations similar to GitHub stats cards.
"""

import json
import requests
from collections import defaultdict, Counter
from datetime import datetime, timedelta, timezone
import argparse
import os
import time
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


class GitHubLanguageAnalyzer:
    def __init__(self, token):
        """
        Initialize the analyzer with a GitHub personal access token.

        Args:
            token (str): GitHub personal access token with appropriate permissions
        """
        self.token = token
        self.base_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        # Rate limiting: GitHub allows 5000 points per hour for GraphQL
        self.request_delay = 0.2  # Increased delay for line count queries

        # GitHub language colors (updated from GitHub's linguist)
        self.language_colors = {
            "Python": "#3572A5",
            "JavaScript": "#f1e05a",
            "TypeScript": "#2b7489",
            "Java": "#b07219",
            "C": "#555555",
            "C++": "#f34b7d",
            "C#": "#239120",
            "Go": "#00ADD8",
            "Rust": "#dea584",
            "Ruby": "#701516",
            "PHP": "#4F5D95",
            "Swift": "#ffac45",
            "Kotlin": "#F18E33",
            "Scala": "#c22d40",
            "Shell": "#89e051",
            "PowerShell": "#012456",
            "HTML": "#e34c26",
            "CSS": "#563d7c",
            "SCSS": "#c6538c",
            "Vue": "#2c3e50",
            "React": "#61dafb",
            "Angular": "#dd0031",
            "Svelte": "#ff3e00",
            "Dart": "#00B4AB",
            "R": "#198CE7",
            "MATLAB": "#e16737",
            "Jupyter Notebook": "#DA5B0B",
            "Dockerfile": "#384d54",
            "YAML": "#cb171e",
            "JSON": "#292929",
            "XML": "#0060ac",
            "Markdown": "#083fa1",
            "LaTeX": "#3D6117",
            "Vim script": "#199f4b",
            "Emacs Lisp": "#c065db",
            "Lua": "#000080",
            "Perl": "#0298c3",
            "Haskell": "#5e5086",
            "Clojure": "#db5855",
            "F#": "#b845fc",
            "OCaml": "#3be133",
            "Erlang": "#B83998",
            "Elixir": "#6e4a7e",
            "Crystal": "#000100",
            "Nim": "#ffc200",
            "Zig": "#ec915c",
            "Assembly": "#6E4C13",
            "VHDL": "#adb2cb",
            "Verilog": "#b2b7f8",
            "SQL": "#e38c00",
            "PLpgSQL": "#336790",
            "Makefile": "#427819",
            "CMake": "#DA3434",
            "Tcl": "#e4cc98",
            "TeX": "#3D6117",
            "Batchfile": "#C1F12E",
            "Visual Basic": "#945db7",
            "VBA": "#867db1",
            "AppleScript": "#101F1F",
            "ActionScript": "#882B0F",
            "CoffeeScript": "#244776",
            "LiveScript": "#499886",
            "Objective-C": "#438eff",
            "Objective-C++": "#6866fb",
            "D": "#ba595e",
            "Pascal": "#E3F171",
            "Fortran": "#4d41b1",
            "COBOL": "#000000",
            "Ada": "#02f88c",
            "Prolog": "#74283c",
            "Scheme": "#1e4aec",
            "Common Lisp": "#3fb68b",
            "Racket": "#3c5caa",
            "Smalltalk": "#596706",
            "Groovy": "#e69f56",
            "Julia": "#a270ba",
            "Hack": "#878787",
            "Processing": "#0096D8",
            "Arduino": "#bd79d1",
            "PureScript": "#1D222D",
            "Elm": "#60B5CC",
            "Reason": "#ff5847",
            "F*": "#572e30",
            "Idris": "#b30000",
            "Agda": "#315665",
            "Coq": "#d0b68c",
            "Lean": "#fff"
        }

    def _make_graphql_request(self, query: str, variables: dict) -> dict:
        """
        Make a GraphQL request with error handling and rate limiting.

        Args:
            query (str): GraphQL query string
            variables (dict): Query variables

        Returns:
            dict: GraphQL response data
        """
        time.sleep(self.request_delay)  # Basic rate limiting

        response = requests.post(
            self.base_url,
            json={"query": query, "variables": variables},
            headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"GraphQL query failed with status {response.status_code}: {response.text}")

        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")

        return data["data"]

    def _parse_iso_date(self, date_str: str) -> datetime:
        """
        Parse ISO date string to timezone-aware datetime object.

        Args:
            date_str (str): ISO format date string

        Returns:
            datetime: Timezone-aware datetime object
        """
        if date_str.endswith('Z'):
            # Replace 'Z' with '+00:00' for proper timezone parsing
            date_str = date_str[:-1] + '+00:00'

        try:
            # Try parsing with timezone info
            return datetime.fromisoformat(date_str)
        except ValueError:
            # Fallback: assume UTC if no timezone info
            dt = datetime.fromisoformat(date_str.replace('Z', ''))
            return dt.replace(tzinfo=timezone.utc)

    def _to_iso_string(self, dt: datetime) -> str:
        """
        Convert datetime to ISO string format expected by GitHub API.

        Args:
            dt (datetime): Datetime object (timezone-aware or naive)

        Returns:
            str: ISO format string ending with 'Z'
        """
        if dt.tzinfo is None:
            # Assume UTC for naive datetime
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to UTC and format
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    def _generate_year_ranges(self, from_date: str, to_date: str) -> List[Tuple[str, str]]:
        """
        Generate year-based date ranges for API calls.

        Args:
            from_date (str): Start date in ISO format
            to_date (str): End date in ISO format

        Returns:
            List[Tuple[str, str]]: List of (start_date, end_date) tuples
        """
        start_dt = self._parse_iso_date(from_date)
        end_dt = self._parse_iso_date(to_date)

        ranges = []
        current_start = start_dt

        while current_start < end_dt:
            # Calculate end of current year or the target end date, whichever is earlier
            year_end = datetime(current_start.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            current_end = min(year_end, end_dt)

            ranges.append((
                self._to_iso_string(current_start),
                self._to_iso_string(current_end)
            ))

            # Move to next year
            current_start = datetime(current_start.year + 1, 1, 1, tzinfo=timezone.utc)

        return ranges

    def get_commit_stats_for_repo(self, repo_owner: str, repo_name: str, username: str,
                                  from_date: str, to_date: str, primary_language: str = "Unknown") -> dict:
        """
        Get detailed commit statistics including line counts for a specific repository.

        Args:
            repo_owner (str): Repository owner
            repo_name (str): Repository name
            username (str): GitHub username to filter commits
            from_date (str): Start date in ISO format
            to_date (str): End date in ISO format
            primary_language (str): Primary language of the repository for display

        Returns:
            dict: Commit statistics with line counts
        """
        query = """
        query($owner: String!, $name: String!, $since: GitTimestamp!, $until: GitTimestamp!) {
          repository(owner: $owner, name: $name) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, since: $since, until: $until) {
                    totalCount
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      oid
                      committedDate
                      author {
                        user {
                          login
                        }
                        email
                        name
                      }
                      additions
                      deletions
                      changedFiles
                      message
                    }
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "owner": repo_owner,
            "name": repo_name,
            "since": from_date,
            "until": to_date
        }

        try:
            data = self._make_graphql_request(query, variables)

            if not data or not data.get("repository") or not data["repository"].get("defaultBranchRef"):
                return {"total_additions": 0, "total_deletions": 0, "commits": []}

            commits = data["repository"]["defaultBranchRef"]["target"]["history"]["nodes"]

            # Filter commits by the specific user
            user_commits = []
            total_additions = 0
            total_deletions = 0

            for commit in commits:
                # Check if commit is by the target user (by login or email/name match)
                is_user_commit = False

                if commit["author"]["user"] and commit["author"]["user"]["login"]:
                    # Direct username match
                    if commit["author"]["user"]["login"].lower() == username.lower():
                        is_user_commit = True
                else:
                    # For commits without linked GitHub user, we'll skip them
                    # as we can't reliably attribute them to the user
                    continue

                if is_user_commit:
                    additions = commit["additions"] or 0
                    deletions = commit["deletions"] or 0

                    user_commits.append({
                        "oid": commit["oid"],
                        "date": commit["committedDate"],
                        "additions": additions,
                        "deletions": deletions,
                        "changed_files": commit["changedFiles"] or 0,
                        "message": commit["message"][:100] + "..." if len(commit["message"]) > 100 else commit[
                            "message"]
                    })

                    total_additions += additions
                    total_deletions += deletions

            return {
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "net_lines": total_additions - total_deletions,
                "commits": user_commits,
                "commit_count": len(user_commits)
            }

        except Exception as e:
            print(
                f"  ⚠️  Warning: Could not fetch detailed stats for {repo_owner}/{repo_name} ({primary_language}): {e}")
            return {"total_additions": 0, "total_deletions": 0, "net_lines": 0, "commits": [], "commit_count": 0}

    def get_user_contributions_range(self, username: str, from_date: str, to_date: str,
                                     include_line_counts: bool = True) -> dict:
        """
        Fetch user contributions across multiple years using data aggregation.

        Args:
            username (str): GitHub username
            from_date (str): Start date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
            to_date (str): End date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
            include_line_counts (bool): Whether to fetch detailed line count statistics

        Returns:
            dict: Aggregated contributions data across all years
        """
        year_ranges = self._generate_year_ranges(from_date, to_date)

        print(f"📅 Fetching data across {len(year_ranges)} year period(s)...")

        aggregated_data = {
            "user": None,
            "contributionsCollection": {
                "startedAt": from_date,
                "endedAt": to_date,
                "hasAnyContributions": False,
                "totalCommitContributions": 0,
                "commitContributionsByRepository": []
            }
        }

        # Track repositories across years to avoid duplicates
        repo_contributions = defaultdict(lambda: {
            "repository": None,
            "contributions": {"nodes": []},
            "line_stats": {"total_additions": 0, "total_deletions": 0, "net_lines": 0}
        })

        for i, (range_start, range_end) in enumerate(year_ranges, 1):
            print(f"  🔄 Fetching year {i}/{len(year_ranges)}: {range_start[:4]} "
                  f"({range_start[:10]} to {range_end[:10]})")

            year_data = self.get_user_contributions_single_year(username, range_start, range_end)

            if not year_data or not year_data.get("user"):
                continue

            # Set user data from first successful response
            if not aggregated_data["user"]:
                aggregated_data["user"] = year_data["user"]

            year_contributions = year_data["user"]["contributionsCollection"]

            # Aggregate totals
            if year_contributions["hasAnyContributions"]:
                aggregated_data["contributionsCollection"]["hasAnyContributions"] = True

            aggregated_data["contributionsCollection"]["totalCommitContributions"] += \
                year_contributions["totalCommitContributions"]

            # Aggregate repository contributions
            for repo_contrib in year_contributions["commitContributionsByRepository"]:
                repo_key = repo_contrib["repository"]["nameWithOwner"]
                repo = repo_contrib["repository"]

                if repo_key not in repo_contributions:
                    repo_contributions[repo_key]["repository"] = repo

                # Merge contribution nodes
                repo_contributions[repo_key]["contributions"]["nodes"].extend(
                    repo_contrib["contributions"]["nodes"]
                )

                # Fetch line count statistics if requested
                if include_line_counts and not repo["isPrivate"]:  # Skip private repos for line counts
                    primary_lang = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "Unknown"
                    print(f"    📊 Fetching line counts for {repo_key} ({primary_lang})")
                    owner, name = repo_key.split('/')
                    line_stats = self.get_commit_stats_for_repo(
                        owner, name, username, range_start, range_end, primary_lang
                    )

                    repo_contributions[repo_key]["line_stats"]["total_additions"] += line_stats["total_additions"]
                    repo_contributions[repo_key]["line_stats"]["total_deletions"] += line_stats["total_deletions"]
                    repo_contributions[repo_key]["line_stats"]["net_lines"] += line_stats["net_lines"]

        # Convert aggregated data back to expected format
        for repo_key, repo_data in repo_contributions.items():
            # Calculate total count for each repository
            total_count = sum(node["commitCount"] for node in repo_data["contributions"]["nodes"])
            repo_data["contributions"]["totalCount"] = total_count

            if total_count > 0:  # Only include repositories with contributions
                aggregated_data["contributionsCollection"]["commitContributionsByRepository"].append(repo_data)

        print(f"✅ Successfully aggregated data from {len(year_ranges)} year period(s)")
        return aggregated_data

    def get_user_contributions_single_year(self, username: str, from_date: str, to_date: str) -> dict:
        """
        Fetch user contributions for a single year period.

        Args:
            username (str): GitHub username
            from_date (str): Start date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
            to_date (str): End date in ISO format (YYYY-MM-DDTHH:MM:SSZ)

        Returns:
            dict: GraphQL response containing contributions data
        """
        query = """
        query($username: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $username) {
            login
            name
            contributionsCollection(from: $from, to: $to) {
              startedAt
              endedAt
              hasAnyContributions
              totalCommitContributions
              commitContributionsByRepository {
                repository {
                  name
                  nameWithOwner
                  owner {
                    login
                  }
                  primaryLanguage {
                    name
                    color
                  }
                  languages(first: 15, orderBy: {field: SIZE, direction: DESC}) {
                    edges {
                      node {
                        name
                        color
                      }
                      size
                    }
                    totalSize
                  }
                  isPrivate
                  isFork
                  createdAt
                  updatedAt
                }
                contributions(first: 100) {
                  totalCount
                  nodes {
                    commitCount
                    occurredAt
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
          }
        }
        """

        variables = {
            "username": username,
            "from": from_date,
            "to": to_date
        }

        return self._make_graphql_request(query, variables)

    def get_user_contributions(self, username: str, from_date: Optional[str] = None,
                               to_date: Optional[str] = None, years_back: int = 1,
                               include_line_counts: bool = True) -> dict:
        """
        Fetch user contributions with support for multiple years.

        Args:
            username (str): GitHub username
            from_date (str, optional): Start date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
            to_date (str, optional): End date in ISO format (YYYY-MM-DDTHH:MM:SSZ)
            years_back (int): Number of years to look back if no dates provided
            include_line_counts (bool): Whether to fetch line count statistics

        Returns:
            dict: GraphQL response containing contributions data
        """
        # If no dates provided, use the specified number of years back
        if not from_date or not to_date:
            # Use current date as of 2025-06-18 00:43:28 UTC
            now = datetime(2025, 6, 18, 0, 43, 28, tzinfo=timezone.utc)
            to_date = self._to_iso_string(now)
            from_date = self._to_iso_string(now - timedelta(days=365 * years_back))

        # Check if date range spans more than one year
        start_dt = self._parse_iso_date(from_date)
        end_dt = self._parse_iso_date(to_date)

        # If range is within one year, use single API call (but still fetch line counts)
        if (end_dt - start_dt).days <= 365 and start_dt.year == end_dt.year:
            data = self.get_user_contributions_single_year(username, from_date, to_date)

            # Add line count statistics for single year
            if include_line_counts and data and data.get("user"):
                print("📊 Fetching line count statistics...")
                for repo_contrib in data["user"]["contributionsCollection"]["commitContributionsByRepository"]:
                    repo = repo_contrib["repository"]
                    if not repo["isPrivate"]:  # Skip private repos
                        repo_key = repo["nameWithOwner"]
                        primary_lang = repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "Unknown"
                        owner, name = repo_key.split('/')
                        print(f"    📊 Fetching line counts for {repo_key} ({primary_lang})")

                        line_stats = self.get_commit_stats_for_repo(
                            owner, name, username, from_date, to_date, primary_lang
                        )

                        repo_contrib["line_stats"] = line_stats
                    else:
                        repo_contrib["line_stats"] = {
                            "total_additions": 0, "total_deletions": 0,
                            "net_lines": 0, "commits": [], "commit_count": 0
                        }

            return data
        else:
            # Use multi-year aggregation
            return self.get_user_contributions_range(username, from_date, to_date, include_line_counts)

    def analyze_languages(self, contributions_data: dict, include_forks: bool = True,
                          include_private: bool = True, min_commits: int = 1) -> dict:
        """
        Analyze languages from contributions data with enhanced filtering and line counts.

        Args:
            contributions_data (dict): Data from get_user_contributions
            include_forks (bool): Whether to include forked repositories
            include_private (bool): Whether to include private repositories
            min_commits (int): Minimum commits required to include a repository

        Returns:
            dict: Analysis results with language statistics and line counts
        """
        if not contributions_data or not contributions_data.get("user"):
            raise Exception("No user data found")

        user = contributions_data["user"]
        contributions = contributions_data["contributionsCollection"]
        commit_contributions = contributions["commitContributionsByRepository"]

        # Language statistics with line count tracking
        language_stats = defaultdict(lambda: {
            "total_commits": 0,
            "weighted_commits": 0,
            "repositories": set(),
            "total_bytes": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "net_lines": 0,
            "color": None,
            "repo_details": []
        })

        total_commits = 0
        total_additions = 0
        total_deletions = 0
        total_repositories = 0
        repository_details = []
        yearly_stats = defaultdict(lambda: defaultdict(int))

        for repo_contribution in commit_contributions:
            repo = repo_contribution["repository"]
            contributions_list = repo_contribution["contributions"]["nodes"]
            line_stats = repo_contribution.get("line_stats", {
                "total_additions": 0, "total_deletions": 0, "net_lines": 0
            })

            # Filter repositories based on preferences
            if not include_forks and repo["isFork"]:
                continue
            if not include_private and repo["isPrivate"]:
                continue

            # Count commits for this repository
            repo_commits = sum(contrib["commitCount"] for contrib in contributions_list)

            if repo_commits < min_commits:
                continue

            total_repositories += 1
            total_commits += repo_commits
            total_additions += line_stats.get("total_additions", 0)
            total_deletions += line_stats.get("total_deletions", 0)

            # Track yearly contributions
            for contrib in contributions_list:
                year = contrib["occurredAt"][:4]
                yearly_stats[year]["total_commits"] += contrib["commitCount"]

            # Primary language
            primary_language = repo["primaryLanguage"]
            if primary_language:
                lang_name = primary_language["name"]
                # Use GitHub's color if available, otherwise use our fallback
                lang_color = primary_language.get("color") or self.language_colors.get(lang_name, "#858585")

                language_stats[lang_name]["total_commits"] += repo_commits
                language_stats[lang_name]["repositories"].add(repo["nameWithOwner"])
                language_stats[lang_name]["color"] = lang_color

                # Add line stats to primary language
                language_stats[lang_name]["total_additions"] += line_stats.get("total_additions", 0)
                language_stats[lang_name]["total_deletions"] += line_stats.get("total_deletions", 0)
                language_stats[lang_name]["net_lines"] += line_stats.get("net_lines", 0)

            # All languages in the repository with weighted calculations
            repo_languages = []
            total_repo_size = repo["languages"]["totalSize"]

            for lang_edge in repo["languages"]["edges"]:
                lang_name = lang_edge["node"]["name"]
                lang_size = lang_edge["size"]
                # Use GitHub's color if available, otherwise use our fallback
                lang_color = lang_edge["node"].get("color") or self.language_colors.get(lang_name, "#858585")

                # Weight commits by language percentage in repository
                lang_percentage = lang_size / total_repo_size if total_repo_size > 0 else 0
                weighted_commits = repo_commits * lang_percentage
                weighted_additions = line_stats.get("total_additions", 0) * lang_percentage
                weighted_deletions = line_stats.get("total_deletions", 0) * lang_percentage
                weighted_net = line_stats.get("net_lines", 0) * lang_percentage

                language_stats[lang_name]["weighted_commits"] += weighted_commits
                language_stats[lang_name]["repositories"].add(repo["nameWithOwner"])
                language_stats[lang_name]["total_bytes"] += lang_size
                language_stats[lang_name]["total_additions"] += weighted_additions
                language_stats[lang_name]["total_deletions"] += weighted_deletions
                language_stats[lang_name]["net_lines"] += weighted_net
                language_stats[lang_name]["color"] = lang_color

                # Track repository details for this language
                language_stats[lang_name]["repo_details"].append({
                    "repo": repo["nameWithOwner"],
                    "commits": repo_commits,
                    "percentage": lang_percentage * 100,
                    "bytes": lang_size,
                    "additions": weighted_additions,
                    "deletions": weighted_deletions,
                    "net_lines": weighted_net
                })

                repo_languages.append({
                    "name": lang_name,
                    "size": lang_size,
                    "percentage": lang_percentage * 100,
                    "color": lang_color
                })

                # Track yearly language stats
                for contrib in contributions_list:
                    year = contrib["occurredAt"][:4]
                    yearly_stats[year][lang_name] += contrib["commitCount"] * lang_percentage

            repository_details.append({
                "name": repo["nameWithOwner"],
                "commits": repo_commits,
                "additions": line_stats.get("total_additions", 0),
                "deletions": line_stats.get("total_deletions", 0),
                "net_lines": line_stats.get("net_lines", 0),
                "primary_language": primary_language["name"] if primary_language else "Unknown",
                "all_languages": repo_languages,
                "is_fork": repo["isFork"],
                "is_private": repo["isPrivate"],
                "created_at": repo["createdAt"],
                "updated_at": repo["updatedAt"]
            })

        # Convert sets to lists and calculate percentages
        final_stats = {}
        for lang, stats in language_stats.items():
            final_stats[lang] = {
                "total_commits": int(stats["total_commits"]),
                "weighted_commits": stats["weighted_commits"],
                "commit_percentage": (stats["total_commits"] / total_commits * 100) if total_commits > 0 else 0,
                "weighted_percentage": (stats["weighted_commits"] / total_commits * 100) if total_commits > 0 else 0,
                "repository_count": len(stats["repositories"]),
                "repositories": list(stats["repositories"]),
                "total_bytes": stats["total_bytes"],
                "total_additions": int(stats["total_additions"]),
                "total_deletions": int(stats["total_deletions"]),
                "net_lines": int(stats["net_lines"]),
                "lines_percentage": (stats["total_additions"] / total_additions * 100) if total_additions > 0 else 0,
                "color": stats["color"],
                "repo_details": stats["repo_details"]
            }

        # Convert yearly stats to regular dict
        yearly_summary = {}
        for year, year_data in yearly_stats.items():
            yearly_summary[year] = dict(year_data)

        return {
            "user": {
                "login": user["login"],
                "name": user["name"]
            },
            "period": {
                "from": contributions["startedAt"],
                "to": contributions["endedAt"]
            },
            "summary": {
                "total_commits": total_commits,
                "total_repositories": total_repositories,
                "total_additions": total_additions,
                "total_deletions": total_deletions,
                "net_lines": total_additions - total_deletions,
                "has_contributions": contributions["hasAnyContributions"],
                "years_analyzed": len(yearly_summary)
            },
            # Sort by weighted_commits (commit percentage) as requested
            "languages": dict(sorted(final_stats.items(), key=lambda x: x[1]["weighted_commits"], reverse=True)),
            "repositories": sorted(repository_details, key=lambda x: x["commits"], reverse=True),
            "yearly_breakdown": yearly_summary
        }

    def get_basic_user_stats(self, username: str) -> dict:
        """
        Get basic user statistics for the terminal display.

        Args:
            username (str): GitHub username

        Returns:
            dict: Basic user statistics
        """
        query = """
        query($username: String!) {
          user(login: $username) {
            login
            name
            bio
            company
            location
            email
            websiteUrl
            createdAt
            followers {
              totalCount
            }
            following {
              totalCount
            }
            repositories(first: 100, privacy: PUBLIC, ownerAffiliations: [OWNER]) {
              totalCount
              nodes {
                stargazerCount
                forkCount
                primaryLanguage {
                  name
                }
                isPrivate
                isFork
              }
            }
            contributionsCollection {
              totalCommitContributions
              totalIssueContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
            }
          }
        }
        """

        variables = {"username": username}
        data = self._make_graphql_request(query, variables)

        if not data or not data.get("user"):
            raise Exception(f"User {username} not found")

        user = data["user"]
        repos = user["repositories"]["nodes"]

        # Calculate stats
        total_stars = sum(repo["stargazerCount"] for repo in repos if not repo["isPrivate"])
        total_forks = sum(repo["forkCount"] for repo in repos if not repo["isPrivate"])
        public_repos = len([repo for repo in repos if not repo["isPrivate"] and not repo["isFork"]])

        # Most used language
        languages = [repo["primaryLanguage"]["name"] for repo in repos
                     if repo["primaryLanguage"] and not repo["isPrivate"]]
        most_used_lang = Counter(languages).most_common(1)[0][0] if languages else "N/A"

        return {
            "login": user["login"],
            "name": user["name"] or user["login"],
            "bio": user["bio"] or "",
            "company": user["company"] or "",
            "location": user["location"] or "",
            "email": user["email"] or "",
            "website": user["websiteUrl"] or "",
            "created_at": user["createdAt"],
            "followers": user["followers"]["totalCount"],
            "following": user["following"]["totalCount"],
            "public_repos": public_repos,
            "total_repos": user["repositories"]["totalCount"],
            "total_stars": total_stars,
            "total_forks": total_forks,
            "total_commits": user["contributionsCollection"]["totalCommitContributions"],
            "total_issues": user["contributionsCollection"]["totalIssueContributions"],
            "total_prs": user["contributionsCollection"]["totalPullRequestContributions"],
            "total_reviews": user["contributionsCollection"]["totalPullRequestReviewContributions"],
            "most_used_language": most_used_lang
        }

    def generate_terminal_svg(self, analysis: dict, user_stats: dict, filename: str,
                              dark_mode: bool = False, max_languages: int = 10) -> str:
        """
        Generate a terminal-style SVG visualization matching the provided design.

        Args:
            analysis (dict): Analysis results from analyze_languages
            user_stats (dict): Basic user statistics
            filename (str): Output filename for the SVG
            dark_mode (bool): Whether to use dark mode colors
            max_languages (int): Maximum number of languages to display

        Returns:
            str: Path to the generated SVG file
        """
        languages = analysis["languages"]
        summary = analysis["summary"]

        # Get top languages
        top_languages = list(languages.items())[:max_languages]

        # Terminal dimensions
        width = 800
        terminal_height = 600

        # Color schemes
        if dark_mode:
            bg_color = "#0d1117"
            terminal_bg = "#161b22"
            border_color = "#30363d"
            text_color = "#e6edf3"
            prompt_color = "#7c3aed"
            cursor_color = "#f0f6fc"
            green_color = "#2ea043"
            red_color = "#da3633"
            yellow_color = "#fb8500"
            blue_color = "#2f81f7"
            gray_color = "#8b949e"
        else:
            bg_color = "#ffffff"
            terminal_bg = "#f6f8fa"
            border_color = "#d0d7de"
            text_color = "#24292f"
            prompt_color = "#8250df"
            cursor_color = "#24292f"
            green_color = "#1f883d"
            red_color = "#cf222e"
            yellow_color = "#d1242f"
            blue_color = "#0969da"
            gray_color = "#656d76"

        # Create SVG root
        svg = ET.Element("svg", {
            "width": str(width),
            "height": str(terminal_height),
            "xmlns": "http://www.w3.org/2000/svg",
            "style": "background-color: transparent;"
        })

        # Background
        bg_rect = ET.SubElement(svg, "rect", {
            "width": str(width),
            "height": str(terminal_height),
            "fill": bg_color,
            "rx": "6"
        })

        # Terminal window
        terminal_rect = ET.SubElement(svg, "rect", {
            "x": "20",
            "y": "20",
            "width": str(width - 40),
            "height": str(terminal_height - 40),
            "fill": terminal_bg,
            "stroke": border_color,
            "stroke-width": "1",
            "rx": "6"
        })

        # Terminal header (title bar)
        header_rect = ET.SubElement(svg, "rect", {
            "x": "20",
            "y": "20",
            "width": str(width - 40),
            "height": "30",
            "fill": border_color if dark_mode else "#e1e4e8",
            "rx": "6 6 0 0"
        })

        # Terminal buttons (red, yellow, green)
        button_colors = ["#ff5f56", "#ffbd2e", "#27ca3f"]
        for i, color in enumerate(button_colors):
            ET.SubElement(svg, "circle", {
                "cx": str(35 + i * 15),
                "cy": "35",
                "r": "4",
                "fill": color
            })

        # Terminal title
        title_text = ET.SubElement(svg, "text", {
            "x": str(width // 2),
            "y": "40",
            "font-family": "SF Mono, Monaco, Inconsolata, Roboto Mono, monospace",
            "font-size": "12",
            "fill": text_color,
            "text-anchor": "middle",
            "font-weight": "500"
        })
        title_text.text = f"{user_stats['login']}@github:~$ github-stats"

        # Content area starts
        content_y = 70
        line_height = 14
        current_y = content_y

        def add_terminal_line(text: str, color: str = text_color, indent: int = 0, bold: bool = False):
            nonlocal current_y
            line_text = ET.SubElement(svg, "text", {
                "x": str(40 + indent * 8),
                "y": str(current_y),
                "font-family": "SF Mono, Monaco, Inconsolata, Roboto Mono, monospace",
                "font-size": "11",
                "fill": color,
                "font-weight": "600" if bold else "400"
            })
            line_text.text = text
            current_y += line_height

        # GitHub Stats header
        add_terminal_line("┌─ GitHub Stats ──────────────────────────────────────────────────┐", border_color,
                          bold=True)
        add_terminal_line("│                                                                 │", border_color)

        # User info
        join_date = datetime.fromisoformat(user_stats['created_at'].replace('Z', '+00:00')).strftime('%Y')
        user_line = f"│  👤 {user_stats['name']} (@{user_stats['login']}) - Joined {join_date}"
        # Pad to 65 characters and add closing border
        user_line = user_line.ljust(65) + "│"
        add_terminal_line(user_line, text_color)

        if user_stats['bio']:
            bio_text = user_stats['bio'][:50]
            if len(user_stats['bio']) > 50:
                bio_text += "..."
            bio_line = f"│  📝 {bio_text}"
            bio_line = bio_line.ljust(65) + "│"
            add_terminal_line(bio_line, gray_color)

        if user_stats['location']:
            location_line = f"│  📍 {user_stats['location'][:50]}"
            location_line = location_line.ljust(65) + "│"
            add_terminal_line(location_line, gray_color)

        add_terminal_line("│                                                                 │", border_color)

        # Stats section
        add_terminal_line("│  📊 Repository Stats:                                           │", blue_color, bold=True)

        # Format stats with proper spacing
        repos_str = str(user_stats['public_repos'])
        stars_str = str(user_stats['total_stars'])
        forks_str = str(user_stats['total_forks'])
        stats_line1 = f"│     Public Repos: {repos_str} │ Total Stars: {stars_str} │ Forks: {forks_str}"
        stats_line1 = stats_line1.ljust(65) + "│"
        add_terminal_line(stats_line1, text_color)

        followers_str = str(user_stats['followers'])
        following_str = str(user_stats['following'])
        stats_line2 = f"│     Followers: {followers_str} │ Following: {following_str}"
        stats_line2 = stats_line2.ljust(65) + "│"
        add_terminal_line(stats_line2, text_color)

        add_terminal_line("│                                                                 │", border_color)

        # Contributions
        add_terminal_line("│  🚀 Contribution Stats:                                        │", green_color, bold=True)

        commits_str = str(summary['total_commits'])
        issues_str = str(user_stats['total_issues'])
        prs_str = str(user_stats['total_prs'])
        contrib_line1 = f"│     Commits: {commits_str} │ Issues: {issues_str} │ PRs: {prs_str}"
        contrib_line1 = contrib_line1.ljust(65) + "│"
        add_terminal_line(contrib_line1, text_color)

        reviews_str = str(user_stats['total_reviews'])
        repos_analyzed_str = str(summary['total_repositories'])
        contrib_line2 = f"│     Reviews: {reviews_str} │ Repositories: {repos_analyzed_str}"
        contrib_line2 = contrib_line2.ljust(65) + "│"
        add_terminal_line(contrib_line2, text_color)

        add_terminal_line("│                                                                 │", border_color)

        # Language analysis header
        add_terminal_line("│  💻 Language Analysis (by commit percentage):                  │", yellow_color, bold=True)
        add_terminal_line("│  ═══════════════════════════════════════════════════════════   │", border_color)

        # Language statistics
        for i, (lang, stats) in enumerate(top_languages):
            if i >= max_languages:
                break

            # Create color indicator
            lang_color = stats["color"] or "#858585"
            commits_formatted = f"{int(stats['weighted_commits']):,}"
            percentage = f"{stats['weighted_percentage']:.1f}%"

            # Language line with proper formatting
            lang_line = f"│  ● {lang} {commits_formatted} commits ({percentage})"
            lang_line = lang_line.ljust(65) + "│"
            add_terminal_line(lang_line, text_color)

            # Add colored dot separately (overwrite the bullet)
            dot = ET.SubElement(svg, "circle", {
                "cx": "45",
                "cy": str(current_y - line_height + 4),
                "r": "3",
                "fill": lang_color
            })

        # Line counts if available
        if summary['total_additions'] > 0:
            add_terminal_line("│                                                                 │", border_color)
            add_terminal_line("│  📈 Code Statistics:                                           │", blue_color,
                              bold=True)

            additions_str = f"{summary['total_additions']:,}"
            deletions_str = f"{summary['total_deletions']:,}"
            lines_line1 = f"│     Lines Added: {additions_str} │ Deleted: {deletions_str}"
            lines_line1 = lines_line1.ljust(65) + "│"
            add_terminal_line(lines_line1, text_color)

            net_change_str = f"{summary['net_lines']:+,}"
            lines_line2 = f"│     Net Change: {net_change_str} lines"
            lines_line2 = lines_line2.ljust(65) + "│"
            add_terminal_line(lines_line2, green_color if summary['net_lines'] >= 0 else red_color)

        add_terminal_line("│                                                                 │", border_color)
        add_terminal_line("└─────────────────────────────────────────────────────────────────┘", border_color,
                          bold=True)

        # Prompt line
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        prompt_line = f"{user_stats['login']}@github:~$ # Generated on {current_time}"
        add_terminal_line(prompt_line, prompt_color)

        # Blinking cursor
        cursor_x = 40 + len(prompt_line) * 6
        cursor = ET.SubElement(svg, "rect", {
            "x": str(cursor_x),
            "y": str(current_y - 12),
            "width": "8",
            "height": "12",
            "fill": cursor_color
        })

        # Add blinking animation
        blink_animate = ET.SubElement(cursor, "animate", {
            "attributeName": "opacity",
            "values": "1;0;1",
            "dur": "1.5s",
            "repeatCount": "indefinite"
        })

        # Write SVG to file
        tree = ET.ElementTree(svg)
        ET.indent(tree, space="  ", level=0)
        tree.write(filename, encoding="utf-8", xml_declaration=True)

        return filename

    def print_analysis(self, analysis: dict, show_yearly: bool = True, top_n: int = 15):
        """
        Print a formatted analysis report with enhanced multi-year insights and line counts.

        Args:
            analysis (dict): Analysis results from analyze_languages
            show_yearly (bool): Whether to show yearly breakdown
            top_n (int): Number of top languages to display
        """
        user = analysis["user"]
        period = analysis["period"]
        summary = analysis["summary"]
        languages = analysis["languages"]
        yearly_breakdown = analysis.get("yearly_breakdown", {})

        print(f"\n🔍 Multi-Year Language Analysis with Line Counts for {user['name']} (@{user['login']})")
        print("=" * 125)
        print(f"📅 Period: {period['from'][:10]} to {period['to'][:10]} ({summary['years_analyzed']} years)")
        print(f"📊 Total Commits: {summary['total_commits']:,}")
        print(f"📚 Total Repositories: {summary['total_repositories']}")
        print(f"➕ Total Lines Added: {summary['total_additions']:,}")
        print(f"➖ Total Lines Deleted: {summary['total_deletions']:,}")
        print(f"📈 Net Lines: {summary['net_lines']:,}")

        if not languages:
            print("\n❌ No language data found for the specified period.")
            return

        print(f"\n🏆 Top {min(top_n, len(languages))} Languages by Commit Percentage:")
        print("=" * 125)
        print(
            f"{'Rank':<5} {'Language':<20} {'Weighted':<12} {'Commit%':<10} {'Lines+':<12} {'Lines-':<12} {'Net':<12} {'Repos':<7} {'Bytes':<10}")
        print(f"{'':5} {'':20} {'Commits':<12} {'':10} {'':12} {'':12} {'':12} {'':7} {'':10}")
        print("=" * 125)

        for i, (lang, stats) in enumerate(list(languages.items())[:top_n], 1):
            color_indicator = f"●" if stats["color"] else "○"
            bytes_formatted = self._format_bytes(stats["total_bytes"])

            print(f"{i:2d}. {color_indicator} {lang:<18} "
                  f"{int(stats['weighted_commits']):>10,} "
                  f"{stats['weighted_percentage']:>8.1f}% "
                  f"{stats['total_additions']:>10,} "
                  f"{stats['total_deletions']:>10,} "
                  f"{stats['net_lines']:>+10,} "
                  f"{stats['repository_count']:>5} "
                  f"{bytes_formatted:>8}")

        # Language distribution chart by commit percentage
        print(f"\n📈 Language Distribution by Commit Percentage (Top 10):")
        print("-" * 60)

        max_weighted = max(stats["weighted_commits"] for stats in languages.values()) if languages else 1

        for lang, stats in list(languages.items())[:10]:
            bar_length = int((stats["weighted_commits"] / max_weighted) * 40)
            bar = "█" * bar_length + "░" * (40 - bar_length)
            print(f"{lang:<15} │{bar}│ {stats['weighted_percentage']:>5.1f}%")

        # Yearly breakdown
        if show_yearly and yearly_breakdown:
            print(f"\n📅 Yearly Contribution Breakdown:")
            print("-" * 50)

            years = sorted(yearly_breakdown.keys())
            for year in years[-5:]:  # Show last 5 years
                year_data = yearly_breakdown[year]
                total_year_commits = year_data.get("total_commits", 0)
                if total_year_commits > 0:
                    print(f"\n{year}: {total_year_commits:,} commits")

                    # Top 3 languages for this year
                    year_langs = [(lang, commits) for lang, commits in year_data.items()
                                  if lang != "total_commits" and commits > 0]
                    year_langs.sort(key=lambda x: x[1], reverse=True)

                    for lang, commits in year_langs[:3]:
                        percentage = (commits / total_year_commits) * 100
                        print(f"  • {lang}: {commits:.0f} commits ({percentage:.1f}%)")

        # Repository insights with line counts
        top_repos = analysis["repositories"][:5]
        if top_repos:
            print(f"\n🏢 Top 5 Most Active Repositories by Commits:")
            print("-" * 80)
            for repo in top_repos:
                fork_indicator = " (fork)" if repo["is_fork"] else ""
                private_indicator = " (private)" if repo["is_private"] else ""
                net_lines = repo["additions"] - repo["deletions"]
                print(f"• {repo['name']}{fork_indicator}{private_indicator}")
                print(
                    f"  {repo['commits']:,} commits, +{repo['additions']:,}/-{repo['deletions']:,} lines (net: {net_lines:+,})")
                print(f"  Primary: {repo['primary_language']}")

    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f}{unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f}TB"

    def save_to_json(self, analysis: dict, filename: str):
        """
        Save analysis results to a JSON file with enhanced data including line counts.

        Args:
            analysis (dict): Analysis results
            filename (str): Output filename
        """
        # Convert sets to lists for JSON serialization
        json_data = json.loads(json.dumps(analysis, default=str))

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Enhanced analysis with line counts saved to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze GitHub user's programming languages and generate terminal-style SVG stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate both light and dark mode terminal SVGs
  python github_language_analyzer.py --years 3 --terminal-svg stats

  # Generate only dark mode SVG
  python github_language_analyzer.py --years 2 --terminal-svg stats --dark-only

  # Analyze without line counts (faster)
  python github_language_analyzer.py --no-line-counts --terminal-svg stats
        """
    )

    parser.add_argument("username", nargs='?', default="Cubik65536",
                        help="GitHub username to analyze (default: Cubik65536)")
    parser.add_argument("--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--from-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="End date (YYYY-MM-DD)")
    parser.add_argument("--years", type=int, default=5,
                        help="Number of years to analyze back from today (default: 1)")
    parser.add_argument("--exclude-forks", action="store_true", help="Exclude forked repositories")
    parser.add_argument("--exclude-private", action="store_true", help="Exclude private repositories")
    parser.add_argument("--min-commits", type=int, default=1,
                        help="Minimum commits required per repository (default: 1)")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--terminal-svg", default="terminal_svg", help="Generate terminal-style SVG (specify base filename)")
    parser.add_argument("--dark-only", action="store_true", help="Generate only dark mode SVG")
    parser.add_argument("--light-only", action="store_true", help="Generate only light mode SVG")
    parser.add_argument("--top-n", type=int, default=15,
                        help="Number of top languages to display (default: 15)")
    parser.add_argument("--no-yearly", action="store_true", help="Skip yearly breakdown display")
    parser.add_argument("--no-line-counts", action="store_true",
                        help="Skip line count analysis (faster execution)")

    args = parser.parse_args()

    # Get token from argument or environment variable
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ Error: GitHub token required. Use --token argument or set GITHUB_TOKEN environment variable.")
        print("   You can create a token at: https://github.com/settings/tokens")
        print("   Required scopes: read:user, repo (for private repos)")
        return 1

    # Convert dates to ISO format if provided
    from_date = None
    to_date = None

    if args.from_date:
        try:
            # Parse as naive datetime and assume UTC
            dt = datetime.strptime(args.from_date, "%Y-%m-%d")
            dt = dt.replace(tzinfo=timezone.utc)
            from_date = dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        except ValueError:
            print("❌ Error: Invalid from-date format. Use YYYY-MM-DD")
            return 1

    if args.to_date:
        try:
            # Parse as naive datetime and assume UTC, set to end of day
            dt = datetime.strptime(args.to_date, "%Y-%m-%d")
            dt = dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            to_date = dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        except ValueError:
            print("❌ Error: Invalid to-date format. Use YYYY-MM-DD")
            return 1

    try:
        analyzer = GitHubLanguageAnalyzer(token)

        print(f"🔄 Fetching contributions for @{args.username}...")
        if from_date and to_date:
            print(f"📅 Date range: {args.from_date} to {args.to_date}")
        else:
            print(f"📅 Analyzing last {args.years} year(s)")

        if not args.no_line_counts:
            print("📊 Including line count analysis (this may take longer)")

        # Get basic user stats
        print("🔄 Fetching user statistics...")
        user_stats = analyzer.get_basic_user_stats(args.username)

        # Get contribution data
        contributions_data = analyzer.get_user_contributions(
            args.username, from_date, to_date, args.years,
            include_line_counts=not args.no_line_counts
        )

        print("🔄 Analyzing languages...")
        analysis = analyzer.analyze_languages(
            contributions_data,
            include_forks=not args.exclude_forks,
            include_private=not args.exclude_private,
            min_commits=args.min_commits
        )

        analyzer.print_analysis(analysis, show_yearly=not args.no_yearly, top_n=args.top_n)

        if args.output:
            analyzer.save_to_json(analysis, args.output)

        if args.terminal_svg:
            print(f"\n🎨 Generating terminal-style SVG visualization...")

            if not args.dark_only:
                # Generate light mode
                light_path = analyzer.generate_terminal_svg(
                    analysis, user_stats, f"{args.terminal_svg}_light.svg",
                    dark_mode=False, max_languages=min(args.top_n, 10)
                )
                print(f"📊 Light mode SVG saved to {light_path}")

            if not args.light_only:
                # Generate dark mode
                dark_path = analyzer.generate_terminal_svg(
                    analysis, user_stats, f"{args.terminal_svg}_dark.svg",
                    dark_mode=True, max_languages=min(args.top_n, 10)
                )
                print(f"📊 Dark mode SVG saved to {dark_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
