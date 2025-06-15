import os
import json
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from tqdm import tqdm


class ExploitTags(BaseModel):
    """Model for structured exploitation technique tags"""
    
    description_tags: List[str] = Field(
        description="Tags describing the vulnerability/technique (prefix with 'desc:')",
        default_factory=list
    )
    prerequisite_tags: List[str] = Field(
        description="Tags for exploitation prerequisites (prefix with 'preq:')", 
        default_factory=list
    )
    result_tags: List[str] = Field(
        description="Tags for exploitation results/capabilities (prefix with 'res:')",
        default_factory=list
    )


@dataclass
class FileAnalysisResult:
    """Result of analyzing a single markdown file"""
    file_path: str
    relative_path: str
    tags: ExploitTags
    error: Optional[str] = None


class CTFWikiTagger:
    """Main class for tagging CTF Wiki exploitation content"""
    
    def __init__(self, api_key: str, api_base: str = "https://api.anthropic.com"):
        """Initialize the tagger with Claude API credentials"""
        self.llm = ChatAnthropic(
            model="claude-opus-4-20250514",
            anthropic_api_key=api_key,
            anthropic_api_url=api_base,
        )
        
        # Create output parser
        self.parser = PydanticOutputParser(pydantic_object=ExploitTags)
        
        # Create the prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a cybersecurity expert analyzing CTF wiki content about exploitation techniques.
            
Your task is to extract specific tags from the content:

1. Description tags (desc:) - What the vulnerability/technique is about
2. Prerequisite tags (preq:) - What conditions/capabilities are needed for exploitation
3. Result tags (res:) - What can be achieved through this exploitation

Guidelines:
- Be very specific and technical
- Use lowercase, hyphenated tags (e.g., heap-overflow, use-after-free)
- For prerequisites, include version requirements (e.g., preq:<libc2.23)
- Focus on actionable, searchable terms
- Extract ALL relevant technical details

e.g:
```house-of-force.md
# House Of Force

## 介绍
House Of Force 属于 House Of XXX 系列的利用方法 House Of XXX 是 2004 年《The Malloc Maleficarum-Glibc Malloc Exploitation Techniques》中提出的一系列针对 glibc 堆分配器的利用方法。
House Of Force 是一种堆利用方法，但是并不是说 House Of Force 必须得基于堆漏洞来进行利用。如果一个堆(heap based) 漏洞想要通过 House Of Force 方法进行利用，需要以下条件：

1. 能够以溢出等方式控制到 top chunk 的 size 域
2. 能够自由地控制堆分配尺寸的大小
```

Tags:
desc:heap, desc:house-of, desc:...
preq:heap-overflow, preq:allocation-size, preq:top-chunk-header-manipulation, preq:<libc2.xx, preq:...
res:write-what-where


{format_instructions}"""),
            ("human", "Analyze this exploitation technique documentation and extract tags:\n\n{content}")
        ])
        
        # Store workspace root for relative path calculation
        self.workspace_root = Path.cwd().parent
    
    def analyze_file(self, file_path: Path) -> FileAnalysisResult:
        """Analyze a single markdown file and extract tags"""
        try:
            # Read the file content
            content = file_path.read_text(encoding='utf-8')
            
            # Skip if file is too small (likely just a stub)
            if len(content.strip()) < 10:
                return FileAnalysisResult(
                    file_path=str(file_path),
                    relative_path=str(file_path.relative_to(self.workspace_root)),
                    tags=ExploitTags(),
                    error="File too small, likely a stub"
                )
            
            # Prepare the messages
            messages = self.prompt.format_messages(
                content=content,  # Limit content length
                format_instructions=self.parser.get_format_instructions()
            )
            
            # Get response from Claude
            response = self.llm.invoke(messages)
            
            # Parse the response
            tags = self.parser.parse(response.content)
            
            # Add prefixes if not present
            tags.description_tags = [
                t if t.startswith('desc:') else f'desc:{t}' 
                for t in tags.description_tags
            ]
            tags.prerequisite_tags = [
                t if t.startswith('preq:') else f'preq:{t}'
                for t in tags.prerequisite_tags
            ]
            tags.result_tags = [
                t if t.startswith('res:') else f'res:{t}'
                for t in tags.result_tags
            ]
            
            return FileAnalysisResult(
                file_path=str(file_path),
                relative_path=str(file_path.relative_to(self.workspace_root)),
                tags=tags
            )
            
        except Exception as e:
            return FileAnalysisResult(
                file_path=str(file_path),
                relative_path=str(file_path.relative_to(self.workspace_root)),
                tags=ExploitTags(),
                error=str(e)
            )
    
    def find_markdown_files(self, root_dir: Path) -> List[Path]:
        """Recursively find all markdown files in the directory"""
        markdown_files = []
        for file_path in root_dir.rglob("*.md"):
            # Skip non-content files
            if any(skip in str(file_path) for skip in ['figure/', 'src/', 'README.md']):
                continue
            markdown_files.append(file_path)
        return markdown_files
    
    def process_directory(self, root_dir: str, max_workers: int = 5) -> Dict[str, Dict]:
        """Process all markdown files in the directory"""
        root_path = Path(root_dir).resolve()
        
        if not root_path.exists():
            raise ValueError(f"Directory {root_dir} does not exist")
        
        # Find all markdown files
        files = self.find_markdown_files(root_path)
        print(f"Found {len(files)} markdown files to process")
        
        results = {}
        errors = []
        
        # Process files with thread pool for parallel processing
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self.analyze_file, file_path): file_path 
                for file_path in files
            }
            
            # Process results as they complete
            with tqdm(total=len(files), desc="Processing files") as pbar:
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    
                    try:
                        result = future.result()
                        
                        if result.error:
                            errors.append({
                                'file': result.relative_path,
                                'error': result.error
                            })
                        else:
                            # Store results
                            results[result.relative_path] = {
                                'description_tags': result.tags.description_tags,
                                'prerequisite_tags': result.tags.prerequisite_tags,
                                'result_tags': result.tags.result_tags,
                                'all_tags': (
                                    result.tags.description_tags +
                                    result.tags.prerequisite_tags +
                                    result.tags.result_tags
                                )
                            }
                    
                    except Exception as e:
                        errors.append({
                            'file': str(file_path),
                            'error': str(e)
                        })
                    
                    pbar.update(1)
        
        return {
            'results': results,
            'errors': errors,
            'summary': {
                'total_files': len(files),
                'successful': len(results),
                'failed': len(errors)
            }
        }


def main():
    """Main function to run the tagger"""
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    api_base = os.getenv('ANTHROPIC_API_BASE')
    
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
    # Initialize tagger
    tagger = CTFWikiTagger(api_key, api_base)
    
    # Process the docs directory
    docs_dir = '../docs/zh/docs'
    
    print(f"Starting analysis of {docs_dir}...")
    results = tagger.process_directory(docs_dir, max_workers=3)
    
    # Save results
    output_file = '../ctf_wiki_tags.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nAnalysis complete!")
    print(f"Results saved to: {output_file}")
    print(f"Summary: {results['summary']}")
    
    # Generate a report
    generate_report(results)


def generate_report(results: Dict[str, Dict]):
    """Generate a markdown report of the tagging results"""
    report = []
    report.append("# CTF Wiki Tagging Report\n")
    report.append(f"## Summary\n")
    report.append(f"- Total files processed: {results['summary']['total_files']}")
    report.append(f"- Successfully tagged: {results['summary']['successful']}")
    report.append(f"- Failed: {results['summary']['failed']}\n")
    
    if results['errors']:
        report.append("## Errors\n")
        for error in results['errors']:
            report.append(f"- **{error['file']}**: {error['error']}")
        report.append("")
    
    report.append("## Tag Statistics\n")
    
    # Collect all tags
    all_desc_tags = []
    all_preq_tags = []
    all_res_tags = []
    
    for file_data in results['results'].values():
        all_desc_tags.extend(file_data['description_tags'])
        all_preq_tags.extend(file_data['prerequisite_tags'])
        all_res_tags.extend(file_data['result_tags'])
    
    # Count occurrences
    from collections import Counter
    desc_counts = Counter(all_desc_tags)
    preq_counts = Counter(all_preq_tags)
    res_counts = Counter(all_res_tags)
    
    report.append("### Most Common Description Tags")
    for tag, count in desc_counts.most_common(10):
        report.append(f"- {tag}: {count}")
    report.append("")
    
    report.append("### Most Common Prerequisite Tags")
    for tag, count in preq_counts.most_common(10):
        report.append(f"- {tag}: {count}")
    report.append("")
    
    report.append("### Most Common Result Tags")
    for tag, count in res_counts.most_common(10):
        report.append(f"- {tag}: {count}")
    report.append("")
    
    report.append("## Sample Tagged Files\n")
    
    # Show first 5 files as examples
    for i, (file_path, tags) in enumerate(list(results['results'].items())[:5]):
        report.append(f"### {file_path}")
        report.append(f"**Description tags**: {', '.join(tags['description_tags'])}")
        report.append(f"**Prerequisite tags**: {', '.join(tags['prerequisite_tags'])}")
        report.append(f"**Result tags**: {', '.join(tags['result_tags'])}")
        report.append("")
    
    # Save report
    report_file = '../ctf_wiki_tags_report.md'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main() 