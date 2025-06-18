#!/usr/bin/env python3
"""
GitHub Profile SVG Generator
Generates neofetch-style profile SVGs with statistics using GitHub GraphQL API
"""

import json
import requests
import argparse
import os
from datetime import datetime, timedelta
from collections import defaultdict
import xml.etree.ElementTree as ET
import unicodedata

# GitHub language colors (subset - add more as needed)
LANGUAGE_COLORS = {
    'Python': '#3572A5',
    'JavaScript': '#f1e05a',
    'TypeScript': '#2b7489',
    'Java': '#b07219',
    'C++': '#f34b7d',
    'C': '#555555',
    'C#': '#239120',
    'Go': '#00ADD8',
    'Rust': '#dea584',
    'Ruby': '#701516',
    'PHP': '#4F5D95',
    'Swift': '#ffac45',
    'Kotlin': '#F18E33',
    'Scala': '#c22d40',
    'HTML': '#e34c26',
    'CSS': '#1572B6',
    'Shell': '#89e051',
    'Dockerfile': '#384d54',
    'YAML': '#cb171e',
    'JSON': '#292929',
    'Markdown': '#083fa1',
    'Vue': '#2c3e50',
    'React': '#61dafb',
    'Jupyter Notebook': '#DA5B0B',
    'R': '#198CE7',
    'MATLAB': '#e16737',
    'Objective-C': '#438eff',
    'Perl': '#0298c3',
    'Lua': '#000080',
    'Dart': '#00B4AB',
    'Haskell': '#5e5086',
    'Clojure': '#db5855',
    'Elixir': '#6e4a7e',
    'Erlang': '#B83998',
    'F#': '#b845fc',
    'OCaml': '#3be133',
    'PowerShell': '#012456',
    'Assembly': '#6E4C13',
    'Vim script': '#199f4b',
    'Makefile': '#427819',
    'CMake': '#DA3434',
    'Batchfile': '#C1F12E',
    'TeX': '#3D6117',
    'Groovy': '#e69f56',
    'ActionScript': '#882B0F',
    'CoffeeScript': '#244776',
    'LiveScript': '#499886',
    'PureScript': '#1D222D',
    'Elm': '#60B5CC',
    'Crystal': '#000100',
    'Nim': '#ffc200',
    'D': '#ba595e',
    'Zig': '#ec915c',
    'V': '#4f87c4',
    'Julia': '#a270ba',
    'Chapel': '#8dc63f',
    'Pike': '#005390',
    'Nix': '#7e7eff',
    'Racket': '#3c5caa',
    'Standard ML': '#dc566d',
    'Smalltalk': '#596706',
    'Ada': '#02f88c',
    'Fortran': '#4d41b1',
    'COBOL': '#005590'
}


def get_profile_content_definition(user_data, top_languages):
    """
    Define the content structure for the profile.

    This function returns a list of tuples defining the content lines to display.
    Each tuple contains (key, value) where:
    - key: The field name or special marker
    - value: The field value or empty string for special cases

    Special markers:
    - "GAP": Adds vertical spacing
    - Keys starting with "—": Section headers
    - "PLACEHOLDER": Will be replaced with actual data during rendering

    Args:
        user_data: GitHub user data from API
        top_languages: List of top programming languages

    Returns:
        List of (key, value) tuples defining the profile content
    """
    # Calculate age for uptime
    created_date = datetime.fromisoformat(user_data['createdAt'].replace('Z', '+00:00'))
    age = datetime.now(created_date.tzinfo) - created_date
    years = age.days // 365
    months = (age.days % 365) // 30
    days = (age.days % 365) % 30

    # Build the content structure
    content_lines = []

    # System info section
    content_lines.extend([
        ("OS", "Windows 10, Android 14, Linux"),
        ("Uptime", f"{years} years, {months} months, {days} days"),
        ("Host", user_data.get("company", "TTM Technologies, Inc.") or "TTM Technologies, Inc."),
        ("Kernel", "CAM (Computer Aided Manufacturing) Operator"),
        ("IDE", "IDEA 2023.3.2, VSCode 1.96.0"),
    ])

    # Add gap before languages section
    content_lines.append(("GAP", ""))

    # Languages section
    content_lines.extend([
        ("Languages.Programming", ", ".join(top_languages) if top_languages else "Java, Python, JavaScript, C++"),
        ("Languages.Computer", "HTML, CSS, JSON, LaTeX, YAML"),
        ("Languages.Real", "English, Spanish"),
    ])

    # Add gap before hobbies section
    content_lines.append(("GAP", ""))

    # Hobbies section
    content_lines.extend([
        ("Hobbies.Software", "Minecraft Modding, iOS Jailbreaking"),
        ("Hobbies.Hardware", "Overclocking, Undervolting"),
    ])

    # Add gap and Contact section header
    content_lines.extend([
        ("GAP", ""),
        ("— Contact ", ""),
    ])

    # Contact info
    content_lines.extend([
        ("Email.Personal", "agrantnmac@gmail.com"),
        ("Email.Personal", "andrew@grant.software"),
        ("Email.Work", "Andrew.Grant@ttmtech.com"),
        ("LinkedIn", "Andrew6rant"),
        ("Discord", "andrew6rant"),
    ])

    # Add gap and GitHub Stats section header
    content_lines.extend([
        ("GAP", ""),
        ("— GitHub Stats ", ""),
    ])

    # GitHub Stats (values will be replaced during rendering)
    content_lines.extend([
        ("Repos", "PLACEHOLDER"),
        ("Commits", "PLACEHOLDER"),
        ("Lines of Code on GitHub", "PLACEHOLDER")
    ])

    return content_lines


class GitHubProfileGenerator:
    def __init__(self, token, username):
        self.token = token
        self.username = username
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        self.graphql_url = 'https://api.github.com/graphql'

    def clean_and_visible_length(self, text):
        """Clean text of invisible characters and return the visible length"""
        if not text:
            return text, 0

        # Remove or normalize invisible characters
        cleaned = ''
        for char in text:
            # Skip zero-width characters and other invisible characters
            if unicodedata.category(char) in ['Cf', 'Mn', 'Me']:  # Format chars, nonspacing marks, enclosing marks
                continue
            # Skip specific invisible characters
            if char in ['\u200b', '\u200c', '\u200d', '\u2060', '\ufeff', '\u202a', '\u202b', '\u202c', '\u202d',
                        '\u202e']:
                continue
            cleaned += char

        # Calculate visual width (some characters may be wider)
        visual_length = 0
        for char in cleaned:
            # Most characters are width 1, but some CJK characters might be width 2
            if unicodedata.east_asian_width(char) in ['F', 'W']:  # Fullwidth or Wide
                visual_length += 2
            else:
                visual_length += 1

        return cleaned, visual_length

    def format_line(self, key, value, total_width=68, separator=":"):
        """Format a line to be exactly the specified width"""
        # Handle special cases for headers
        if key.startswith('—') or key.startswith('-'):
            # This is a header line
            return key + '—' * (total_width - len(key))

        # Regular key-value pair
        key_part = f". {key}{separator}"
        value_part = f" {value}"

        # Calculate dots needed
        dots_needed = total_width - len(key_part) - len(value_part)
        if dots_needed < 1:
            # If too long, truncate value
            available_for_value = total_width - len(key_part) - 1
            value_part = f" {value[:available_for_value - 3]}..."
            dots_needed = 1

        return f"{key_part}{'.' * dots_needed}{value_part}"

    def format_username_header(self, full_name, username, total_width=68):
        """Format the username header line to be exactly the specified width"""
        # Clean the full name and get its visual length
        cleaned_name, name_visual_length = self.clean_and_visible_length(full_name)

        # Format: "Full Name -—- @username -——————————————————————-—-"
        username_part = f"@{username}"
        fixed_parts = " -—- " + username_part + " -"  # The fixed separator parts
        end_part = "—-—-"

        # Calculate visual length needed
        fixed_length = len(fixed_parts) + len(end_part)
        available_for_name = total_width - fixed_length

        # If the cleaned name is too long, truncate it
        if name_visual_length > available_for_name:
            # Truncate character by character until it fits
            truncated_name = ""
            current_length = 0
            for char in cleaned_name:
                char_width = 2 if unicodedata.east_asian_width(char) in ['F', 'W'] else 1
                if current_length + char_width + 3 > available_for_name:  # +3 for "..."
                    truncated_name += "..."
                    break
                truncated_name += char
                current_length += char_width
            cleaned_name = truncated_name
            name_visual_length = current_length + (3 if truncated_name.endswith("...") else 0)

        start_part = cleaned_name + fixed_parts

        # Calculate how many — characters needed in the middle
        middle_dashes_needed = total_width - len(start_part) - len(end_part)

        # Adjust for visual length differences (if any wide characters affect the calculation)
        visual_adjustment = name_visual_length - len(cleaned_name.replace("...", "")) - (
            3 if "..." in cleaned_name else 0)
        middle_dashes_needed -= visual_adjustment

        if middle_dashes_needed < 0:
            middle_dashes_needed = 0

        return f"{start_part}{'—' * middle_dashes_needed}{end_part}"

    def format_styled_line(self, key, value, special_styling=None):
        """Format and style a line in one step"""
        # Handle headers first
        if key.startswith('—') or key.startswith('-'):
            header_line = key + '—' * (68 - len(key))
            return f'<tspan class="separator">{header_line}</tspan>'

        # Format the regular line to 68 characters
        key_part = f". {key}:"
        value_part = f" {value}"
        dots_needed = 68 - len(key_part) - len(value_part)

        if dots_needed < 1:
            # If too long, truncate value
            available_for_value = 68 - len(key_part) - 1
            value_part = f" {value[:available_for_value - 3]}..."
            dots_needed = 1

        dots = '.' * dots_needed

        # Apply special styling if provided
        if special_styling and key in special_styling:
            styled_value = special_styling[key](value)
        else:
            styled_value = f'<tspan class="value">{value}</tspan>'

        return f'. <tspan class="key">{key}</tspan>: {dots}{styled_value}'

    def get_content_lines(self, user, language_percentages):
        """Get content lines using the profile content definition function"""
        # Top languages for display (up to 4)
        top_languages = []
        if language_percentages:
            top_languages = list(language_percentages.keys())[:4]

        # Use the external content definition function
        return get_profile_content_definition(user, top_languages)

    def get_user_data_multi_year(self, years_back=5):
        """Fetch user data across multiple years"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * years_back)

        # Get basic user info
        user_query = """
        query($username: String!) {
            user(login: $username) {
                name
                login
                email
                bio
                company
                location
                websiteUrl
                twitterUsername
                followers {
                    totalCount
                }
                following {
                    totalCount
                }
                repositories(ownerAffiliations: [OWNER]) {
                    totalCount
                }
                repositoriesContributedTo {
                    totalCount
                }
                starredRepositories {
                    totalCount
                }
                createdAt
            }
        }
        """

        print(f"Fetching basic user info for {self.username}...")
        response = requests.post(
            self.graphql_url,
            json={'query': user_query, 'variables': {'username': self.username}},
            headers=self.headers
        )

        if response.status_code != 200:
            raise Exception(f"GraphQL query failed with status {response.status_code}: {response.text}")

        response_data = response.json()
        if 'errors' in response_data:
            raise Exception(f"GraphQL errors: {response_data['errors']}")

        if not response_data.get('data') or not response_data['data'].get('user'):
            raise Exception(f"User '{self.username}' not found or no access permissions")

        user_data = response_data['data']['user']
        print(f"✓ Found user: {user_data['name'] or user_data['login']}")

        # Get contribution data for multiple years
        contributions_data = {}
        total_commits = 0
        language_stats = defaultdict(lambda: {
            'commits': 0,
            'additions': 0,
            'deletions': 0,
            'color': '#000000'
        })

        # Fetch data year by year to avoid API limits
        current_year = end_date.year
        for year in range(current_year - years_back + 1, current_year + 1):
            year_start = f"{year}-01-01T00:00:00Z"
            year_end = f"{year}-12-31T23:59:59Z"

            print(f"Fetching contributions for {year}...")

            # Fixed query with proper pagination
            contributions_query = """
            query($username: String!, $from: DateTime!, $to: DateTime!) {
                user(login: $username) {
                    contributionsCollection(from: $from, to: $to) {
                        totalCommitContributions
                        commitContributionsByRepository {
                            repository {
                                name
                                owner {
                                    login
                                }
                                primaryLanguage {
                                    name
                                    color
                                }
                                languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
                                    edges {
                                        size
                                        node {
                                            name
                                            color
                                        }
                                    }
                                }
                            }
                            contributions(first: 100) {
                                totalCount
                                nodes {
                                    commitCount
                                    occurredAt
                                }
                            }
                        }
                    }
                }
            }
            """

            response = requests.post(
                self.graphql_url,
                json={
                    'query': contributions_query,
                    'variables': {
                        'username': self.username,
                        'from': year_start,
                        'to': year_end
                    }
                },
                headers=self.headers
            )

            if response.status_code != 200:
                print(f"⚠ Warning: Failed to fetch data for {year}: {response.status_code}")
                continue

            response_data = response.json()
            if 'errors' in response_data:
                print(f"⚠ Warning: GraphQL errors for {year}: {response_data['errors']}")
                continue

            if not response_data.get('data') or not response_data['data'].get('user'):
                print(f"⚠ Warning: No user data returned for {year}")
                continue

            user_contrib = response_data['data']['user']
            if not user_contrib.get('contributionsCollection'):
                print(f"⚠ Warning: No contributions collection for {year}")
                continue

            year_data = user_contrib['contributionsCollection']
            contributions_data[year] = year_data
            year_commits = year_data.get('totalCommitContributions', 0)
            total_commits += year_commits
            print(f"  ✓ {year}: {year_commits} commits")

            # Process language statistics
            commit_contribs = year_data.get('commitContributionsByRepository', [])
            if not commit_contribs:
                print(f"  No repository contributions found for {year}")
                continue

            for repo_contrib in commit_contribs:
                if not repo_contrib or not repo_contrib.get('repository'):
                    continue

                repo = repo_contrib['repository']
                contributions = repo_contrib.get('contributions', {})
                commit_count = contributions.get('totalCount', 0) if contributions else 0

                if commit_count == 0:
                    continue

                # Get primary language
                primary_lang = repo.get('primaryLanguage')
                if primary_lang and primary_lang.get('name'):
                    lang_name = primary_lang['name']
                    lang_color = primary_lang.get('color') or LANGUAGE_COLORS.get(lang_name, '#000000')
                    language_stats[lang_name]['commits'] += commit_count
                    language_stats[lang_name]['color'] = lang_color

                # Process all languages in repo (weighted by usage)
                languages = repo.get('languages', {})
                if languages and languages.get('edges'):
                    total_size = sum(edge.get('size', 0) for edge in languages['edges'] if edge and edge.get('size'))
                    if total_size > 0:
                        for edge in languages['edges']:
                            if not edge or not edge.get('node'):
                                continue

                            node = edge['node']
                            lang_name = node.get('name')
                            if not lang_name:
                                continue

                            lang_color = node.get('color') or LANGUAGE_COLORS.get(lang_name, '#000000')
                            edge_size = edge.get('size', 0)
                            lang_proportion = edge_size / total_size
                            weighted_commits = int(commit_count * lang_proportion)

                            if weighted_commits > 0:
                                language_stats[lang_name]['commits'] += weighted_commits
                                language_stats[lang_name]['color'] = lang_color
                                # Estimate additions/deletions (rough approximation)
                                language_stats[lang_name]['additions'] += int(edge_size * 0.3)
                                language_stats[lang_name]['deletions'] += int(edge_size * 0.1)

        print(f"✓ Total commits collected: {total_commits}")
        print(f"✓ Languages found: {len(language_stats)}")

        return {
            'user': user_data,
            'total_commits': total_commits,
            'language_stats': dict(language_stats),
            'contributions_data': contributions_data
        }

    def calculate_language_percentages(self, language_stats):
        """Calculate language usage percentages based on commits"""
        total_commits = sum(lang['commits'] for lang in language_stats.values())
        if total_commits == 0:
            return {}

        percentages = {}
        for lang, stats in language_stats.items():
            if stats['commits'] > 0:
                percentages[lang] = {
                    'percentage': (stats['commits'] / total_commits) * 100,
                    'commits': stats['commits'],
                    'additions': stats['additions'],
                    'deletions': stats['deletions'],
                    'net': stats['additions'] - stats['deletions'],
                    'color': stats['color']
                }

        # Sort by percentage
        return dict(sorted(percentages.items(), key=lambda x: x[1]['percentage'], reverse=True))

    def generate_language_bar(self, language_percentages, width=400):
        """Generate SVG elements for language progress bar"""
        if not language_percentages:
            return []

        elements = []
        x_offset = 0

        for lang, stats in language_percentages.items():
            segment_width = (stats['percentage'] / 100) * width
            if segment_width < 1:  # Skip very small segments
                continue

            # Create colored rectangle for this language
            rect = f'<rect x="{x_offset}" y="0" width="{segment_width:.1f}" height="10" fill="{stats["color"]}" rx="1"/>'
            elements.append(rect)
            x_offset += segment_width

        return elements

    def generate_svg(self, data, mode='dark'):
        """Generate the complete SVG"""
        user = data['user']
        language_percentages = self.calculate_language_percentages(data['language_stats'])

        # Calculate total lines of code
        total_additions = sum(lang['additions'] for lang in data['language_stats'].values())
        total_deletions = sum(lang['deletions'] for lang in data['language_stats'].values())
        net_lines = total_additions - total_deletions

        # Color schemes
        if mode == 'dark':
            bg_color = '#0d1117'
            text_color = '#c9d1d9'
            key_color = '#ffa657'
            value_color = '#a5d6ff'
            add_color = '#3fb950'
            del_color = '#f85149'
            separator_color = text_color  # Set separator to same as text color
            green_color = '#238636'
            red_color = '#da3633'
        else:
            bg_color = '#f6f8fa'
            text_color = '#24292f'
            key_color = '#953800'
            value_color = '#0a3069'
            add_color = '#1a7f37'
            del_color = '#cf222e'
            separator_color = text_color  # Set separator to same as text color
            green_color = '#1a7f37'
            red_color = '#cf222e'

        # Constants for layout calculation
        svg_width = 1000
        line_height = 22
        ascii_height = 460  # Height of ASCII art section
        top_margin = 35

        # Dynamically calculate content lines
        content_lines = self.get_content_lines(user, language_percentages)

        # Count different types of lines
        text_lines_count = len([line for line in content_lines if line[0] != "GAP"])
        gap_lines_count = len([line for line in content_lines if line[0] == "GAP"])

        # Count language details (top 6 languages shown)
        language_details_count = min(6, len(language_percentages)) if language_percentages else 0

        # Calculate total content lines
        total_content_lines = (
                1 +  # User header
                text_lines_count +
                gap_lines_count +
                language_details_count
        )

        # Calculate content height (no spacing before language bar, increased spacing after)
        content_height = (
                top_margin +  # Initial margin
                25 +  # Space after user header
                (total_content_lines * line_height) +  # All text lines
                10 +  # Language bar height
                35 +  # Space between language bar and language details (increased from 25)
                15  # Space after language details
        )

        # Take the maximum of ASCII art height and content height, add some padding
        svg_height = max(ascii_height + top_margin, content_height) + 20

        print(f"Debug: Content lines: {len(content_lines)}, Language details: {language_details_count}")
        print(f"Debug: Total lines: {total_content_lines}, SVG height: {svg_height}")

        # Start building SVG with updated font and styling
        svg_content = f'''<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="'Monaspace Krypton',monospace" width="{svg_width}px" height="{svg_height}px" font-size="14px">
<style>
@import url("https://cdn.jsdelivr.net/gh/iXORTech/webfonts@main/monaspace/krypton/krypton.css");
.key {{fill: {key_color}; font-weight: bold;}}
.value {{fill: {value_color};}}
.addColor {{fill: {add_color};}}
.delColor {{fill: {del_color};}}
.separator {{fill: {separator_color};}}
.green {{fill: {green_color};}}
.red {{fill: {red_color};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{svg_width}px" height="{svg_height}px" fill="{bg_color}" rx="15"/>'''

        # ASCII art positioned at x=50
        ascii_x = 50
        svg_content += f'''
<text x="{ascii_x}" y="30" fill="{text_color}" class="ascii">
    <tspan x="{ascii_x}" y="50">                  @</tspan>
    <tspan x="{ascii_x}" y="70">              @@    @@</tspan>
    <tspan x="{ascii_x}" y="90">           @@@        @@@</tspan>
    <tspan x="{ascii_x}" y="110">        @-     @@  @@      @</tspan>
    <tspan x="{ascii_x}" y="130">     @ @#       @@@@       @@ @</tspan>
    <tspan x="{ascii_x}" y="150">  %      +@@ @@      @@ @@+      @</tspan>
    <tspan x="{ascii_x}" y="170">*@@      :@@ @@      @@ @@+      @@*</tspan>
    <tspan x="{ascii_x}" y="190">%<tspan class="green">-</tspan>#@@@%@-       @@@@       .@#@@##<tspan class="red">=</tspan>%</tspan>
    <tspan x="{ascii_x}" y="210">@<tspan class="green">=**+-</tspan>@@@:    #@@  @@.    -@%@<tspan class="red">*+++=</tspan>%</tspan>
    <tspan x="{ascii_x}" y="230">@<tspan class="green">*-=+-</tspan>@<tspan class="green">:*</tspan>@@@@@        @@@@##<tspan class="red">-</tspan>@<tspan class="red">=+==+</tspan>@</tspan>
    <tspan x="{ascii_x}" y="250">@<tspan class="green">-</tspan>@@@<tspan class="green">:</tspan>@<tspan class="green">:**=-</tspan>@<tspan class="green">*</tspan>@@    @@#@<tspan class="red">+=++-</tspan>@<tspan class="red">=</tspan>#@@<tspan class="red">=</tspan>%</tspan>
    <tspan x="{ascii_x}" y="270">@<tspan class="green">--==</tspan>@@@<tspan class="green">=---</tspan>@<tspan class="green">:+%</tspan>@@@%#<tspan class="red">+-</tspan>@<tspan class="red">+===</tspan>#@@<tspan class="red">+===</tspan>@</tspan>
    <tspan x="{ascii_x}" y="290">@<tspan class="green">-=**:</tspan>@<tspan class="green">:</tspan>@@@<tspan class="green">-</tspan>@<tspan class="green">:**=</tspan>%%<tspan class="red">=*+=</tspan>@<tspan class="red">+</tspan>@@@<tspan class="red">-</tspan>@<tspan class="red">=+++=</tspan>%</tspan>
    <tspan x="{ascii_x}" y="310">@@<tspan class="green">%=-:</tspan>@<tspan class="green">:=--*</tspan>@@<tspan class="green">*-:</tspan>##<tspan class="red">-=+</tspan>@@#<tspan class="red">==+-</tspan>@<tspan class="red">-=+#</tspan>@%</tspan>
    <tspan x="{ascii_x}" y="330">@<tspan class="green">-=</tspan>@@#@<tspan class="green">:=*+=</tspan>@<tspan class="green">:</tspan>#@@@@@@#<tspan class="red">=</tspan>@<tspan class="red">++++-</tspan>@<tspan class="red">*</tspan>@@<tspan class="red">+=</tspan>%</tspan>
    <tspan x="{ascii_x}" y="350">@<tspan class="green">=+=-:</tspan>@@@<tspan class="green">=-:</tspan>@<tspan class="green">:+-:%</tspan>#<tspan class="red">-=+=</tspan>@<tspan class="red">==+</tspan>@@@<tspan class="red">-==+=</tspan>@</tspan>
    <tspan x="{ascii_x}" y="370">@<tspan class="green">++**:</tspan>@<tspan class="green">:-</tspan>@@@@<tspan class="green">:-+=</tspan>@@<tspan class="red">=+=-</tspan>@@@@<tspan class="red">=-</tspan>@<tspan class="red">=++-:</tspan>#</tspan>
    <tspan x="{ascii_x}" y="390"> @@@<tspan class="green">*:</tspan>@<tspan class="green">:+=::</tspan>@@@<tspan class="green">+:</tspan>##<tspan class="red">=+</tspan>@@@<tspan class="red">==++=</tspan>@<tspan class="red">---</tspan>%</tspan>
    <tspan x="{ascii_x}" y="410">    @@@<tspan class="green">=+==-</tspan>@<tspan class="green">.-</tspan>#@@@@#<tspan class="red">=-</tspan>@<tspan class="red">+++-.</tspan>@%</tspan>
    <tspan x="{ascii_x}" y="430">        @@<tspan class="green">=-</tspan>@<tspan class="green">:++:*</tspan>#<tspan class="red">-++=</tspan>@<tspan class="red">=:=</tspan>#</tspan>
    <tspan x="{ascii_x}" y="450">           @@<tspan class="green">-:::%</tspan>@<tspan class="red">==-:</tspan>%%</tspan>
    <tspan x="{ascii_x}" y="470">              @@<tspan class="green">:+</tspan>*<tspan class="red">:%</tspan>@</tspan>
    <tspan x="{ascii_x}" y="490">                  *</tspan>
</text>'''

        # Main content starts at x=400
        x_main = 400
        y_start = top_margin

        # User header - use dash format for all usernames, handling invisible characters
        display_name = user.get('name') or user.get('login', 'Unknown')
        username = user.get('login', 'Unknown')

        # Always use the dash format for every username
        header_line = self.format_username_header(display_name, username, 68)

        svg_content += f'''
<text x="{x_main}" y="{y_start}" fill="{text_color}" font-size="14px">
<tspan x="{x_main}" y="{y_start}">{header_line}</tspan>
</text>'''

        y_current = y_start + 25

        # Get stats with safe access
        repos_owned = user.get('repositories', {}).get('totalCount', 0) if user.get('repositories') else 0
        repos_contributed = user.get('repositoriesContributedTo', {}).get('totalCount', 0) if user.get(
            'repositoriesContributedTo') else 0
        stars = user.get('starredRepositories', {}).get('totalCount', 0) if user.get('starredRepositories') else 0
        followers = user.get('followers', {}).get('totalCount', 0) if user.get('followers') else 0

        # Define special styling for lines with colored content
        special_styling = {
            "Lines of Code on GitHub": lambda
                value: f'<tspan class="value">{net_lines:,} ( <tspan class="addColor">{total_additions:,}++</tspan>,  <tspan class="delColor">{total_deletions:,}--</tspan> )</tspan>'
        }

        # Render all content lines dynamically
        for key, value in content_lines:
            if key == "GAP":
                # Add gap (just increase y_current)
                y_current += line_height
                continue

            # Replace placeholder values for stats
            if key == "Repos":
                value = f"{repos_owned} {{Contributed: {repos_contributed}}} | Stars: {stars}"
            elif key == "Commits":
                value = f"{data['total_commits']:,} | Followers: {followers}"
            elif key == "Lines of Code on GitHub":
                value = f"{net_lines:,} ( {total_additions:,}++,  {total_deletions:,}-- )"

            styled_line = self.format_styled_line(key, value, special_styling)
            svg_content += f'''
<text x="{x_main}" y="{y_current}" fill="{text_color}" font-size="14px">
<tspan x="{x_main}" y="{y_current}">{styled_line}</tspan>
</text>'''
            y_current += line_height

        # Language progress bar and stats (no spacing before bar)
        if language_percentages:
            # Add progress bar - wider for 1000px SVG
            svg_content += f'<g transform="translate({x_main}, {y_current})">'
            bar_elements = self.generate_language_bar(language_percentages, 500)
            for element in bar_elements:
                svg_content += f'  {element}'
            svg_content += '</g>'

            y_current += 35  # Spacing after language bar before language details

            # Language details
            for i, (lang, stats) in enumerate(list(language_percentages.items())[:6]):  # Show top 6 languages
                percentage_str = f"{stats['percentage']:.1f}%"
                commits_str = f"{stats['commits']:,} commits"
                lines_str = f"(+{stats['additions']:,} -{stats['deletions']:,})"

                svg_content += f'''
<text x="{x_main}" y="{y_current}" fill="{text_color}" font-size="14px">
<tspan x="{x_main}" y="{y_current}">  <tspan style="fill:{stats['color']}">●</tspan> <tspan class="key">{lang}</tspan>: <tspan class="value">{percentage_str}</tspan> <tspan class="value">{commits_str}</tspan> <tspan class="value">{lines_str}</tspan></tspan>
</text>'''
                y_current += line_height

        svg_content += '\n</svg>'

        return svg_content


def main():
    parser = argparse.ArgumentParser(description='Generate GitHub profile SVGs with language statistics')
    parser.add_argument('--token', help='GitHub Personal Access Token (defaults to GITHUB_TOKEN env var)')
    parser.add_argument('--username', required=True, help='GitHub username')
    parser.add_argument('--years', type=int, default=5, help='Number of years of data to fetch (default: 5)')
    parser.add_argument('--output-dark', default='profile_dark.svg', help='Output file for dark mode SVG')
    parser.add_argument('--output-light', default='profile_light.svg', help='Output file for light mode SVG')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')

    args = parser.parse_args()

    # Get token from argument or environment variable
    token = args.token or os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GitHub token is required. Provide it via --token argument or GITHUB_TOKEN environment variable.")
        return 1

    try:
        print(f"Fetching GitHub data for {args.username}...")
        generator = GitHubProfileGenerator(token, args.username)

        print(f"Collecting {args.years} years of contribution data...")
        data = generator.get_user_data_multi_year(args.years)

        print("Generating dark mode SVG...")
        dark_svg = generator.generate_svg(data, mode='dark')
        with open(args.output_dark, 'w', encoding='utf-8') as f:
            f.write(dark_svg)

        print("Generating light mode SVG...")
        light_svg = generator.generate_svg(data, mode='light')
        with open(args.output_light, 'w', encoding='utf-8') as f:
            f.write(light_svg)

        print(f"\nGenerated successfully!")
        print(f"Dark mode: {args.output_dark}")
        print(f"Light mode: {args.output_light}")

        # Print some statistics
        language_stats = generator.calculate_language_percentages(data['language_stats'])
        if language_stats:
            print(f"\nTop languages:")
            for i, (lang, stats) in enumerate(list(language_stats.items())[:5]):
                print(f"  {i + 1}. {lang}: {stats['percentage']:.1f}% ({stats['commits']:,} commits)")
        else:
            print("\nNo language statistics found.")

    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())