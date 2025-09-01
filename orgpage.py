#!/usr/bin/env python3
"""
Python port of org-page HTML conversion functionality.
Converts org-mode files to HTML with support for:
- Basic org syntax (headings, lists, code blocks, etc.)
- Metadata extraction (title, date, tags, categories)
- Template rendering
- RSS generation
- Tag and category index pages
- Static file copying
"""

import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import html


@dataclass
class OrgMetadata:
    """Holds metadata extracted from org file headers."""

    title: str = ""
    date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    author: str = ""
    description: str = ""
    uri: str = ""
    keywords: List[str] = field(default_factory=list)


@dataclass
class SiteConfig:
    """Site configuration."""

    domain: str = "https://example.com"
    title: str = "My Site"
    subtitle: str = ""
    author: str = ""
    email: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    theme: str = "default"

    # Analytics and comments
    google_analytics_id: str = ""
    disqus_shortname: str = ""

    # Paths
    static_dir: str = "static"
    theme_dir: str = "themes"


class OrgParser:
    """Parses org-mode files and converts them to HTML."""

    def __init__(self):
        self.metadata = OrgMetadata()
        self.content_html = ""
        self.toc_html = ""

    def parse_file(self, file_path: Path) -> Tuple[OrgMetadata, str, str]:
        """Parse an org file and return metadata, content HTML, and TOC HTML."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.metadata = self._extract_metadata(content)
        content_without_metadata = self._remove_metadata_lines(content)
        self.content_html, self.toc_html = self._convert_to_html(
            content_without_metadata
        )

        return self.metadata, self.content_html, self.toc_html

    def _extract_metadata(self, content: str) -> OrgMetadata:
        """Extract metadata from org file headers."""
        metadata = OrgMetadata()

        # Extract #+TITLE:, #+DATE:, etc.
        title_match = re.search(r"^\s*#\+TITLE:\s*(.+)$", content, re.MULTILINE)
        if title_match:
            metadata.title = title_match.group(1).strip()

        date_match = re.search(r"^\s*#\+DATE:\s*(.+)$", content, re.MULTILINE)
        if date_match:
            date_str = date_match.group(1).strip()
            metadata.date = self._parse_date(date_str)

        tags_match = re.search(r"^\s*#\+TAGS:\s*(.+)$", content, re.MULTILINE)
        if tags_match:
            metadata.tags = [tag.strip() for tag in tags_match.group(1).split()]

        categories_match = re.search(
            r"^\s*#\+CATEGORIES?:\s*(.+)$", content, re.MULTILINE
        )
        if categories_match:
            metadata.categories = [
                cat.strip() for cat in categories_match.group(1).split()
            ]

        author_match = re.search(r"^\s*#\+AUTHOR:\s*(.+)$", content, re.MULTILINE)
        if author_match:
            metadata.author = author_match.group(1).strip()

        desc_match = re.search(r"^\s*#\+DESCRIPTION:\s*(.+)$", content, re.MULTILINE)
        if desc_match:
            metadata.description = desc_match.group(1).strip()

        uri_match = re.search(r"^\s*#\+URI:\s*(.+)$", content, re.MULTILINE)
        if uri_match:
            metadata.uri = uri_match.group(1).strip()

        keywords_match = re.search(r"^\s*#\+KEYWORDS:\s*(.+)$", content, re.MULTILINE)
        if keywords_match:
            metadata.keywords = [
                kw.strip() for kw in keywords_match.group(1).split(",")
            ]

        return metadata

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        # Remove org-mode date brackets
        date_str = re.sub(r"[<>\[\]]", "", date_str)

        # Try different date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %a",
            "%Y-%m-%d %a %H:%M",
            "%m/%d/%Y",
            "%d.%m.%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _remove_metadata_lines(self, content: str) -> str:
        """Remove metadata lines from content."""
        lines = content.split("\n")
        filtered_lines = []

        for line in lines:
            if not re.match(r"^\s*#\+[A-Z_]+:", line):
                filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _convert_to_html(self, content: str) -> Tuple[str, str]:
        """Convert org content to HTML."""
        lines = content.split("\n")
        html_lines = []
        toc_entries = []
        in_code_block = False
        current_list_level = 0
        list_stack = []  # Track nested lists

        i = 0
        while i < len(lines):
            line = lines[i]

            # Handle code blocks
            if line.strip().startswith("#+BEGIN_SRC") or line.strip().startswith(
                "#+begin_src"
            ):
                in_code_block = True
                lang_match = re.search(r"#+BEGIN_SRC\s+(\w+)", line, re.IGNORECASE)
                lang = lang_match.group(1) if lang_match else ""
                html_lines.append(f'<pre class="src src-{lang}"><code>')
                i += 1
                continue
            elif line.strip().startswith("#+END_SRC") or line.strip().startswith(
                "#+end_src"
            ):
                in_code_block = False
                html_lines.append("</code></pre>")
                i += 1
                continue
            elif in_code_block:
                html_lines.append(html.escape(line))
                i += 1
                continue

            # Handle quote blocks
            if line.strip().startswith("#+BEGIN_QUOTE") or line.strip().startswith(
                "#+begin_quote"
            ):
                html_lines.append("<blockquote>")
                i += 1
                continue
            elif line.strip().startswith("#+END_QUOTE") or line.strip().startswith(
                "#+end_quote"
            ):
                html_lines.append("</blockquote>")
                i += 1
                continue

            # Handle headings
            heading_match = re.match(r"^(\*+)\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(1).strip()

                # Generate anchor
                anchor = re.sub(r"[^\w\s-]", "", title).strip().lower()
                anchor = re.sub(r"[-\s]+", "-", anchor)

                html_lines.append(
                    f'<h{level} id="{anchor}">{self._process_inline_markup(title)}</h{level}>'
                )
                toc_entries.append((level, title, anchor))
                i += 1
                continue

            # Handle lists
            list_match = re.match(r"^(\s*)[-+*]\s+(.+)$", line)
            if list_match:
                indent = len(list_match.group(1))
                content = list_match.group(2)

                level = indent // 2 + 1  # Convert spaces to list level

                # Handle list nesting
                while current_list_level < level:
                    html_lines.append("<ul>")
                    list_stack.append("ul")
                    current_list_level += 1

                while current_list_level > level:
                    html_lines.append(f"</{list_stack.pop()}>")
                    current_list_level -= 1

                html_lines.append(f"<li>{self._process_inline_markup(content)}</li>")
                i += 1
                continue

            # Handle numbered lists
            num_list_match = re.match(r"^(\s*)(\d+)\.?\s+(.+)$", line)
            if num_list_match:
                indent = len(num_list_match.group(1))
                content = num_list_match.group(3)

                level = indent // 2 + 1

                while current_list_level < level:
                    html_lines.append("<ol>")
                    list_stack.append("ol")
                    current_list_level += 1

                while current_list_level > level:
                    html_lines.append(f"</{list_stack.pop()}>")
                    current_list_level -= 1

                html_lines.append(f"<li>{self._process_inline_markup(content)}</li>")
                i += 1
                continue

            # Close any open lists if we're not in a list anymore
            if not (list_match or num_list_match) and current_list_level > 0:
                while list_stack:
                    html_lines.append(f"</{list_stack.pop()}>")
                    current_list_level -= 1

            # Handle horizontal rules
            if re.match(r"^\s*-{5,}\s*$", line):
                html_lines.append("<hr />")
                i += 1
                continue

            # Handle tables
            if line.strip().startswith("|") and "|" in line.strip()[1:]:
                table_html, lines_consumed = self._parse_table(lines[i:])
                html_lines.append(table_html)
                i += lines_consumed
                continue

            # Handle paragraphs
            if line.strip():
                html_lines.append(f"<p>{self._process_inline_markup(line)}</p>")
            else:
                html_lines.append("")

            i += 1

        # Close any remaining open lists
        while list_stack:
            html_lines.append(f"</{list_stack.pop()}>")

        content_html = "\n".join(html_lines)
        toc_html = self._generate_toc(toc_entries)

        return content_html, toc_html

    def _process_inline_markup(self, text: str) -> str:
        """Process inline org markup like *bold*, /italic/, etc."""
        # Bold
        text = re.sub(r"\*([^*]+)\*", r"<strong>\1</strong>", text)

        # Italic
        text = re.sub(r"/([^/]+)/", r"<em>\1</em>", text)

        # Underline
        text = re.sub(r"_([^_]+)_", r"<u>\1</u>", text)

        # Strike-through
        text = re.sub(r"\+([^+]+)\+", r"<del>\1</del>", text)

        # Code
        text = re.sub(r"=([^=]+)=", r"<code>\1</code>", text)
        text = re.sub(r"~([^~]+)~", r"<code>\1</code>", text)

        # Links [[url][description]] or [[url]]
        text = re.sub(r"\[\[([^\]]+)\]\[([^\]]+)\]\]", r'<a href="\1">\2</a>', text)
        text = re.sub(r"\[\[([^\]]+)\]\]", r'<a href="\1">\1</a>', text)

        return text

    def _parse_table(self, lines: List[str]) -> Tuple[str, int]:
        """Parse org-mode table and return HTML table and number of lines consumed."""
        table_lines = []
        i = 0

        # Collect table lines
        while i < len(lines) and lines[i].strip().startswith("|"):
            line = lines[i].strip()
            if not re.match(r"^\|[\s-+:]+\|$", line):  # Skip separator lines
                table_lines.append(line)
            i += 1

        if not table_lines:
            return "", i

        html = ["<table>"]

        # First row is header
        if table_lines:
            header = table_lines[0]
            cells = [
                cell.strip() for cell in header.split("|")[1:-1]
            ]  # Remove empty first/last
            html.append("<thead><tr>")
            for cell in cells:
                html.append(f"<th>{self._process_inline_markup(cell)}</th>")
            html.append("</tr></thead>")

        # Remaining rows are body
        if len(table_lines) > 1:
            html.append("<tbody>")
            for row in table_lines[1:]:
                cells = [cell.strip() for cell in row.split("|")[1:-1]]
                html.append("<tr>")
                for cell in cells:
                    html.append(f"<td>{self._process_inline_markup(cell)}</td>")
                html.append("</tr>")
            html.append("</tbody>")

        html.append("</table>")

        return "\n".join(html), i

    def _generate_toc(self, toc_entries: List[Tuple[int, str, str]]) -> str:
        """Generate table of contents HTML."""
        if not toc_entries:
            return ""

        html = ['<div id="table-of-contents">']
        html.append("<h2>Table of Contents</h2>")
        html.append('<div id="text-table-of-contents">')

        current_level = 0
        stack = []

        for level, title, anchor in toc_entries:
            while current_level < level:
                html.append("<ul>")
                stack.append("ul")
                current_level += 1

            while current_level > level:
                html.append(f"</{stack.pop()}>")
                current_level -= 1

            html.append(f'<li><a href="#{anchor}">{title}</a></li>')

        # Close remaining tags
        while stack:
            html.append(f"</{stack.pop()}>")

        html.append("</div>")
        html.append("</div>")

        return "\n".join(html)


class TemplateEngine:
    """Simple template engine for rendering HTML pages using Python string formatting."""

    def __init__(self, theme_dir: Path):
        self.theme_dir = theme_dir
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load template files."""
        template_files = {
            "post": "post.html",
            "page": "page.html",
            "index": "index.html",
            "tag": "tag.html",
            "category": "category.html",
            "rss": "rss.xml",
        }

        for name, filename in template_files.items():
            template_path = self.theme_dir / filename
            if template_path.exists():
                with open(template_path, "r", encoding="utf-8") as f:
                    self.templates[name] = f.read()
            else:
                self.templates[name] = self._get_default_template(name)

    def _get_default_template(self, template_name: str) -> str:
        """Get default template if theme template doesn't exist."""
        if template_name == "post":
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {site_title}</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{keywords}">
    <meta name="author" content="{author}">
    {date_meta}
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{site_title}</a></h1>
        {site_subtitle_html}
    </header>
    <main>
        <article>
            <header>
                <h1>{title}</h1>
                {date_html}
                {tags_html}
                {categories_html}
            </header>
            {toc}
            <div class="content">{body}</div>
        </article>
    </main>
    <footer>
        <p>&copy; {year} {site_author}. All rights reserved.</p>
    </footer>
</body>
</html>"""

        elif template_name == "page":
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {site_title}</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{keywords}">
    <meta name="author" content="{author}">
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{site_title}</a></h1>
        {site_subtitle_html}
    </header>
    <main>
        <article>
            <header>
                <h1>{title}</h1>
            </header>
            {toc}
            <div class="content">{body}</div>
        </article>
    </main>
    <footer>
        <p>&copy; {year} {site_author}. All rights reserved.</p>
    </footer>
</body>
</html>"""

        elif template_name == "index":
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{site_title}</title>
    <meta name="description" content="{site_description}">
    <meta name="author" content="{site_author}">
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{site_title}</a></h1>
        {site_subtitle_html}
    </header>
    <main>
        <h1>Recent Posts</h1>
        {posts_html}
    </main>
    <footer>
        <p>&copy; {year} {site_author}. All rights reserved.</p>
    </footer>
</body>
</html>"""

        elif template_name == "tag":
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Posts tagged "{tag}" - {site_title}</title>
    <meta name="author" content="{site_author}">
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{site_title}</a></h1>
    </header>
    <main>
        <h1>Posts tagged "{tag}"</h1>
        {posts_html}
    </main>
    <footer>
        <p>&copy; {year} {site_author}. All rights reserved.</p>
    </footer>
</body>
</html>"""

        elif template_name == "category":
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Posts in category "{category}" - {site_title}</title>
    <meta name="author" content="{site_author}">
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <header>
        <h1><a href="/">{site_title}</a></h1>
    </header>
    <main>
        <h1>Posts in category "{category}"</h1>
        {posts_html}
    </main>
    <footer>
        <p>&copy; {year} {site_author}. All rights reserved.</p>
    </footer>
</body>
</html>"""

        elif template_name == "rss":
            return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>{site_title}</title>
    <link>{site_domain}</link>
    <description>{site_description}</description>
    <lastBuildDate>{last_build_date}</lastBuildDate>
    {items_xml}
</channel>
</rss>"""

        return self.templates.get("page", "")

    def render(self, template_name: str, **context) -> str:
        """Render template with context using simple Python string formatting."""
        template = self.templates.get(template_name, self.templates.get("page", ""))

        # Set defaults for missing values
        safe_context = {}
        for key, value in context.items():
            if value is None:
                safe_context[key] = ""
            else:
                safe_context[key] = str(value)

        return template.format(**safe_context)


class OrgPageConverter:
    """Main converter class."""

    def __init__(self, config: SiteConfig):
        self.config = config
        self.parser = OrgParser()
        self.posts = []
        self.pages = []
        self.tags = {}
        self.categories = {}

    def convert_directory(self, input_dir: Path, output_dir: Path):
        """Convert a directory of org files to HTML."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        # Setup template engine
        theme_dir = input_dir / self.config.theme_dir / self.config.theme
        if not theme_dir.exists():
            theme_dir = Path(__file__).parent / "themes" / self.config.theme
            if not theme_dir.exists():
                theme_dir = Path(__file__).parent / "themes" / "default"
                theme_dir.mkdir(parents=True, exist_ok=True)

        template_engine = TemplateEngine(theme_dir)

        # Process org files
        for org_file in input_dir.rglob("*.org"):
            if org_file.name.startswith("."):
                continue

            rel_path = org_file.relative_to(input_dir)
            self._process_org_file(org_file, rel_path, output_dir, template_engine)

        # Generate index pages
        self._generate_index_pages(output_dir, template_engine)

        # Generate tag and category pages
        self._generate_tag_pages(output_dir, template_engine)
        self._generate_category_pages(output_dir, template_engine)

        # Generate RSS feed
        self._generate_rss_feed(output_dir, template_engine)

        # Copy static files
        self._copy_static_files(input_dir, output_dir)

        print(f"Converted {len(self.posts)} posts and {len(self.pages)} pages")

    def _process_org_file(
        self,
        org_file: Path,
        rel_path: Path,
        output_dir: Path,
        template_engine: TemplateEngine,
    ):
        """Process a single org file."""
        try:
            metadata, content_html, toc_html = self.parser.parse_file(org_file)

            # Determine if this is a post or page based on path or metadata
            is_post = (
                "blog" in str(rel_path).lower()
                or "post" in str(rel_path).lower()
                or metadata.date
            )

            # Generate output path
            if metadata.uri:
                output_path = output_dir / metadata.uri.lstrip("/")
                if output_path.suffix == "":  # if it's just a folder
                    output_path = output_path / "index.html"
            else:
                output_path = output_dir / rel_path.with_suffix("") / "index.html"

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare template data
            template_data = {
                "title": metadata.title or rel_path.stem,
                "body": content_html,
                "toc": toc_html if toc_html else "",
                "author": metadata.author or self.config.author,
                "description": metadata.description or "",
                "keywords": ", ".join(metadata.keywords + self.config.keywords),
                "site_title": self.config.title,
                "site_subtitle": self.config.subtitle or "",
                "site_subtitle_html": f"<p>{self.config.subtitle}</p>"
                if self.config.subtitle
                else "",
                "site_author": self.config.author,
                "site_domain": self.config.domain,
                "site_description": self.config.description or "",
                "year": datetime.now().year,
                "uri": "/" + str(output_path.relative_to(output_dir)),
                "date_meta": "",
                "date_html": "",
                "date_formatted": "",
                "date_rss": "",
                "tags_html": "",
                "categories_html": "",
            }

            # Add date information if available
            if metadata.date:
                template_data.update(
                    {
                        "date_meta": f'<meta name="date" content="{metadata.date.isoformat()}">',
                        "date_html": f'<time datetime="{metadata.date.isoformat()}">{metadata.date.strftime("%B %d, %Y")}</time>',
                        "date_formatted": metadata.date.strftime("%B %d, %Y"),
                        "date_rss": metadata.date.strftime("%a, %d %b %Y %H:%M:%S %z")
                        if metadata.date.tzinfo
                        else metadata.date.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                    }
                )

            # Add tags HTML
            if metadata.tags:
                tag_links = [
                    f'<span class="tag"><a href="/tags/{tag}.html">{tag}</a></span>'
                    for tag in metadata.tags
                ]
                template_data["tags_html"] = (
                    f'<div class="tags">Tags: {" ".join(tag_links)}</div>'
                )

            # Add categories HTML
            if metadata.categories:
                cat_links = [
                    f'<span class="category"><a href="/categories/{cat}.html">{cat}</a></span>'
                    for cat in metadata.categories
                ]
                template_data["categories_html"] = (
                    f'<div class="categories">Categories: {" ".join(cat_links)}</div>'
                )

            # Render template
            template_name = "post" if is_post else "page"
            html = template_engine.render(template_name, **template_data)

            # Write HTML file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

            # Store entry for later use (index pages, RSS, etc.)
            entry = {
                "metadata": metadata,
                "template_data": template_data,
                "output_path": output_path,
                "rel_path": rel_path,
            }

            if is_post:
                self.posts.append(entry)

                # Add to tags and categories
                for tag in metadata.tags:
                    if tag not in self.tags:
                        self.tags[tag] = []
                    self.tags[tag].append(entry)

                for category in metadata.categories:
                    if category not in self.categories:
                        self.categories[category] = []
                    self.categories[category].append(entry)
            else:
                self.pages.append(entry)

        except Exception as e:
            print(f"Error processing {org_file}: {e}")
            import traceback

            traceback.print_exc()

    def _generate_index_pages(self, output_dir: Path, template_engine: TemplateEngine):
        """Generate index pages."""
        # Sort posts by date (newest first)
        sorted_posts = sorted(
            [p for p in self.posts if p["metadata"].date],
            key=lambda x: x["metadata"].date,
            reverse=True,
        )

        # Generate posts HTML
        posts_html_parts = []
        for post in sorted_posts[:10]:  # Latest 10 posts
            data = post["template_data"]
            post_html = f'''
                <article class="post-preview">
                    <h2><a href="{data["uri"]}">{data["title"]}</a></h2>
                    {data["date_html"]}
                    {f"<p>{data['description']}</p>" if data["description"] else ""}
                </article>
            '''
            posts_html_parts.append(post_html.strip())

        template_data = {
            "site_title": self.config.title,
            "site_subtitle": self.config.subtitle,
            "site_subtitle_html": f"<p>{self.config.subtitle}</p>"
            if self.config.subtitle
            else "",
            "site_author": self.config.author,
            "site_domain": self.config.domain,
            "site_description": self.config.description,
            "title": self.config.title,
            "posts_html": "\n".join(posts_html_parts),
            "year": datetime.now().year,
        }

        html = template_engine.render("index", **template_data)

        with open(output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(html)

    def _generate_tag_pages(self, output_dir: Path, template_engine: TemplateEngine):
        """Generate tag index pages."""
        tags_dir = output_dir / "tags"
        tags_dir.mkdir(exist_ok=True)

        for tag, posts in self.tags.items():
            # Generate posts HTML
            posts_html_parts = []
            for post in posts:
                data = post["template_data"]
                post_html = f'''
                    <article class="post-preview">
                        <h2><a href="{data["uri"]}">{data["title"]}</a></h2>
                        {data["date_html"]}
                        {f"<p>{data['description']}</p>" if data["description"] else ""}
                    </article>
                '''
                posts_html_parts.append(post_html.strip())

            template_data = {
                "site_title": self.config.title,
                "site_author": self.config.author,
                "site_domain": self.config.domain,
                "title": f'Posts tagged "{tag}"',
                "tag": tag,
                "posts_html": "\n".join(posts_html_parts),
                "year": datetime.now().year,
            }

            html = template_engine.render("tag", **template_data)

            with open(tags_dir / f"{tag}.html", "w", encoding="utf-8") as f:
                f.write(html)

    def _generate_category_pages(
        self, output_dir: Path, template_engine: TemplateEngine
    ):
        """Generate category index pages."""
        categories_dir = output_dir / "categories"
        categories_dir.mkdir(exist_ok=True)

        for category, posts in self.categories.items():
            # Generate posts HTML
            posts_html_parts = []
            for post in posts:
                data = post["template_data"]
                post_html = f'''
                    <article class="post-preview">
                        <h2><a href="{data["uri"]}">{data["title"]}</a></h2>
                        {data["date_html"]}
                        {f"<p>{data['description']}</p>" if data["description"] else ""}
                    </article>
                '''
                posts_html_parts.append(post_html.strip())

            template_data = {
                "site_title": self.config.title,
                "site_author": self.config.author,
                "site_domain": self.config.domain,
                "title": f'Posts in category "{category}"',
                "category": category,
                "posts_html": "\n".join(posts_html_parts),
                "year": datetime.now().year,
            }

            html = template_engine.render("category", **template_data)

            with open(categories_dir / f"{category}.html", "w", encoding="utf-8") as f:
                f.write(html)

    def _generate_rss_feed(self, output_dir: Path, template_engine: TemplateEngine):
        """Generate RSS feed."""
        # Sort posts by date (newest first)
        sorted_posts = sorted(
            [p for p in self.posts if p["metadata"].date],
            key=lambda x: x["metadata"].date,
            reverse=True,
        )

        # Generate RSS items XML
        items_xml_parts = []
        for post in sorted_posts[:20]:  # Latest 20 posts
            data = post["template_data"]
            # Handle missing description
            description = data.get("description", "")
            if not description:
                description = "No description available"

            item_xml = f"""
    <item>
        <title>{html.escape(data["title"])}</title>
        <link>{self.config.domain}{data["uri"]}</link>
        <description>{html.escape(description)}</description>
        <pubDate>{data.get("date_rss", "")}</pubDate>
        <guid>{self.config.domain}{data["uri"]}</guid>
    </item>"""
            items_xml_parts.append(item_xml.strip())

        template_data = {
            "site_title": html.escape(self.config.title),
            "site_description": html.escape(self.config.description),
            "site_domain": self.config.domain,
            "last_build_date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "items_xml": "\n".join(items_xml_parts),
        }

        rss_xml = template_engine.render("rss", **template_data)

        with open(output_dir / "rss.xml", "w", encoding="utf-8") as f:
            f.write(rss_xml)

    def _copy_static_files(self, input_dir: Path, output_dir: Path):
        """Copy static files (CSS, JS, images, etc.)."""
        static_dir = input_dir / self.config.static_dir
        if static_dir.exists():
            output_static = output_dir / self.config.static_dir
            if output_static.exists():
                shutil.rmtree(output_static)
            shutil.copytree(static_dir, output_static)

        # Copy theme static files
        theme_static = input_dir / self.config.theme_dir / self.config.theme / "static"
        if theme_static.exists():
            for item in theme_static.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(theme_static)
                    dest = output_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)


def create_default_config(config_path: Path | None = None) -> SiteConfig:
    """Create default configuration file."""
    config = SiteConfig()

    if config_path:
        # Here you could load from a config file (JSON, YAML, etc.)
        # For now, just return default config
        pass

    return config


def create_sample_theme(output_dir: Path):
    """Create a sample theme with basic CSS and templates."""
    theme_dir = output_dir / "themes" / "default"
    theme_dir.mkdir(parents=True, exist_ok=True)

    # Create basic CSS
    css_dir = theme_dir / "static" / "css"
    css_dir.mkdir(parents=True, exist_ok=True)

    css_content = """/* Basic theme styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: Georgia, serif;
    line-height: 1.6;
    color: #333;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background-color: #fff;
}

header {
    border-bottom: 2px solid #eee;
    padding-bottom: 20px;
    margin-bottom: 30px;
}

header h1 a {
    text-decoration: none;
    color: #333;
}

header h1 a:hover {
    color: #666;
}

main {
    min-height: 60vh;
}

article {
    margin-bottom: 40px;
}

article header {
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

article header h1 {
    margin-bottom: 10px;
}

article header time {
    color: #666;
    font-style: italic;
}

.tags, .categories {
    margin-top: 10px;
}

.tag, .category {
    background-color: #f4f4f4;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.9em;
    margin-right: 5px;
}

.content h1, .content h2, .content h3, .content h4, .content h5, .content h6 {
    margin-top: 30px;
    margin-bottom: 15px;
}

.content p {
    margin-bottom: 15px;
}

.content ul, .content ol {
    margin-bottom: 15px;
    margin-left: 30px;
}

.content li {
    margin-bottom: 5px;
}

.content code {
    background-color: #f4f4f4;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
}

.content pre {
    background-color: #f4f4f4;
    padding: 15px;
    border-radius: 5px;
    overflow-x: auto;
    margin-bottom: 15px;
}

.content pre code {
    background-color: transparent;
    padding: 0;
}

.content blockquote {
    border-left: 4px solid #ddd;
    margin-left: 0;
    padding-left: 20px;
    color: #666;
    font-style: italic;
}

.content table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 15px;
}

.content table th,
.content table td {
    border: 1px solid #ddd;
    padding: 8px;
    text-align: left;
}

.content table th {
    background-color: #f4f4f4;
    font-weight: bold;
}

#table-of-contents {
    background-color: #f9f9f9;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 30px;
}

#table-of-contents h2 {
    margin-top: 0;
    margin-bottom: 10px;
}

#table-of-contents ul {
    list-style-type: none;
    margin-left: 0;
}

#table-of-contents ul ul {
    margin-left: 20px;
}

#table-of-contents a {
    text-decoration: none;
    color: #333;
}

#table-of-contents a:hover {
    text-decoration: underline;
}

.post-preview {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid #eee;
}

.post-preview h2 {
    margin-bottom: 10px;
}

.post-preview h2 a {
    text-decoration: none;
    color: #333;
}

.post-preview h2 a:hover {
    color: #666;
}

footer {
    border-top: 2px solid #eee;
    padding-top: 20px;
    margin-top: 40px;
    text-align: center;
    color: #666;
    font-size: 0.9em;
}

/* Responsive design */
@media (max-width: 600px) {
    body {
        padding: 10px;
    }

    .content ul, .content ol {
        margin-left: 20px;
    }
}
"""

    with open(css_dir / "style.css", "w", encoding="utf-8") as f:
        f.write(css_content)


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Convert org-mode files to HTML static site"
    )
    parser.add_argument("input_dir", help="Input directory containing org files")
    parser.add_argument("output_dir", help="Output directory for HTML files")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--site-title", default="My Site", help="Site title")
    parser.add_argument(
        "--site-domain", default="https://example.com", help="Site domain"
    )
    parser.add_argument("--site-author", default="", help="Site author")
    parser.add_argument("--theme", default="default", help="Theme name")
    parser.add_argument(
        "--create-sample-theme",
        action="store_true",
        help="Create a sample theme in the input directory",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist")
        return 1

    # Create sample theme if requested
    if args.create_sample_theme:
        create_sample_theme(input_dir)
        print(f"Sample theme created in {input_dir / 'themes' / 'default'}")

    # Create configuration
    config = create_default_config(args.config if args.config else None)
    config.title = args.site_title
    config.domain = args.site_domain
    config.author = args.site_author
    config.theme = args.theme

    # Convert site
    converter = OrgPageConverter(config)
    converter.convert_directory(input_dir, output_dir)

    print(f"Site generated in '{output_dir}'")
    return 0


if __name__ == "__main__":
    exit(main())
