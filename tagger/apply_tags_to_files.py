import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from tqdm import tqdm


def extract_title_from_markdown(content: str) -> Optional[str]:
    """Extract the first H1 heading from markdown content as title"""
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# ') and not line.startswith('##'):
            return line[2:].strip()
    return None


def create_url_from_path(file_path: Path) -> str:
    """Create a URL path from the file path"""
    # Remove docs/zh/docs prefix and .md extension
    path_parts = file_path.parts
    if 'docs' in path_parts:
        idx = path_parts.index('docs')
        # Skip to after 'docs/zh/docs'
        if idx + 2 < len(path_parts) and path_parts[idx+1] == 'zh' and path_parts[idx+2] == 'docs':
            path_parts = path_parts[idx+3:]
        else:
            path_parts = path_parts[idx+1:]
    
    # Remove .md extension from last part
    if path_parts:
        parts_list = list(path_parts)
        parts_list[-1] = parts_list[-1].replace('.md', '')
        path_parts = tuple(parts_list)
    
    # Create URL
    return '/' + '/'.join(path_parts)


def has_frontmatter(content: str) -> bool:
    """Check if markdown content already has YAML frontmatter"""
    return content.strip().startswith('---')


def extract_existing_frontmatter(content: str) -> tuple[Dict, str]:
    """Extract existing frontmatter and return it with the remaining content"""
    if not has_frontmatter(content):
        return {}, content
    
    lines = content.split('\n')
    if lines[0].strip() != '---':
        return {}, content
    
    # Find the closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break
    
    if end_idx is None:
        return {}, content
    
    # Parse YAML frontmatter
    yaml_content = '\n'.join(lines[1:end_idx])
    try:
        frontmatter = yaml.safe_load(yaml_content) or {}
    except:
        frontmatter = {}
    
    # Return frontmatter and remaining content
    remaining_content = '\n'.join(lines[end_idx+1:])
    return frontmatter, remaining_content


def apply_tags_to_file(file_path: Path, tags: Dict[str, List[str]], backup: bool = True) -> bool:
    """Apply tags to a single markdown file"""
    try:
        # Read the file
        content = file_path.read_text(encoding='utf-8')
        
        # Extract existing frontmatter if any
        existing_frontmatter, main_content = extract_existing_frontmatter(content)
        
        # Extract title if not in existing frontmatter
        if 'title' not in existing_frontmatter:
            title = extract_title_from_markdown(main_content)
            if title:
                existing_frontmatter['title'] = title
        
        # Create URL if not in existing frontmatter
        if 'url' not in existing_frontmatter:
            existing_frontmatter['url'] = create_url_from_path(file_path)
        
        # Merge tags - combine all tag types WITH prefixes (desc:, preq:, res:)
        all_tags = []
        for tag in tags.get('description_tags', []):
            # Keep desc: prefix
            if tag not in all_tags:
                all_tags.append(tag)
        
        for tag in tags.get('prerequisite_tags', []):
            # Keep preq: prefix
            if tag not in all_tags:
                all_tags.append(tag)
        
        for tag in tags.get('result_tags', []):
            # Keep res: prefix
            if tag not in all_tags:
                all_tags.append(tag)
        
        # Don't add existing tags - we're replacing them
        # This ensures we start fresh with the new extracted tags
        
        existing_frontmatter['tags'] = sorted(all_tags)
        
        # Create new content with frontmatter
        new_content = "---\n"
        new_content += yaml.dump(existing_frontmatter, allow_unicode=True, sort_keys=False)
        new_content += "---\n"
        new_content += main_content
        
        # Backup original file if requested
        if backup:
            backup_path = file_path.with_suffix('.md.bak')
            backup_path.write_text(content, encoding='utf-8')
        
        # Write the new content
        file_path.write_text(new_content, encoding='utf-8')
        
        return True
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function to apply tags to all files"""
    # Load the tags
    tags_file = Path('../ctf_wiki_tags.json')
    if not tags_file.exists():
        print(f"Tags file not found: {tags_file}")
        print("Please run tag_extractor.py first to generate tags.")
        return
    
    with open(tags_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    results = data.get('results', {})
    
    print(f"Found tags for {len(results)} files")
    
    # Process each file
    successful = 0
    failed = 0
    
    workspace_root = Path.cwd().parent
    
    with tqdm(total=len(results), desc="Applying tags") as pbar:
        for relative_path, tags in results.items():
            file_path = workspace_root / relative_path
            
            if not file_path.exists():
                print(f"File not found: {file_path}")
                failed += 1
            else:
                if apply_tags_to_file(file_path, tags, backup=True):
                    successful += 1
                else:
                    failed += 1
            
            pbar.update(1)
    
    print(f"\nComplete!")
    print(f"Successfully processed: {successful} files")
    print(f"Failed: {failed} files")
    print("\nBackup files created with .bak extension")
    print("\nYour markdown files now have library-mcp compatible frontmatter!")
    print("Tags include prefixes (desc:, preq:, res:) to indicate their type.")
    
    # Show a sample
    if successful > 0:
        print("\nSample processed file:")
        # Get the first successful file
        for relative_path in results:
            file_path = workspace_root / relative_path
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                lines = content.split('\n')
                print(f"\n{relative_path}:")
                print('\n'.join(lines[:20]))
                if len(lines) > 20:
                    print("...")
                break


if __name__ == "__main__":
    main() 