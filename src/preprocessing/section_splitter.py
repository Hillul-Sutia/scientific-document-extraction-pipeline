import re
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class SectionSplitter:
    def _extract_markdown_heading(self, line: str):
        match = re.match(r'^(#{1,6})\s+(.*)', line)
        if match:
            return match.group(2).strip()
        return None

    def _extract_bold_heading(self, line: str):
        match = re.match(r'^\*\*(.+?)\*\*$', line)
        if match:
            return match.group(1).strip()
        return None
    
    

    def split(self, markdown: str) -> dict:
        """
        Split markdown into sections based on headings.
        Returns dictionary:
        {
            section_title: section_content
        }
        """

        sections = {}
        current_section = "UNSPECIFIED"
        current_content = []

        lines = markdown.split("\n")

        for line in lines:
            stripped = line.strip()

            # Detect markdown headings (#, ##, ###)
            heading = self._extract_markdown_heading(stripped)

            # Detect bold headings (**Heading**)
            if not heading:
                heading = self._extract_bold_heading(stripped)
                # logger.info(heading)

            if heading:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                current_section = heading
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        # logger.info(sections.keys())
        # sections = { k:v for k,v in sections.items() if len(v)!=0  }

        # sections = { k:v for k,v in sections.items() if 'reference' not in k.lower() }

        # sections = { k : v for k, v in sections.items() if k != 'UNSPECIFIED'}

        # sections = { k : v for k, v in sections.items() if not k.startswith('==>')  }

        # sections = { k : v for k, v in sections.items() if any( p not in k.lower() for p in ['citing','citation'])  }

        # sections = { k : v for k, v in sections.items() if any( p not in v.lower() for p in ['citing','citation'])  }

        # return sections

        req_sections = dict()
        add_section = False
        remove_section = False

        for k,v in sections.items():
            if 'introduction' in k.lower():
                req_sections[k] = v
                add_section = True
                continue
            
            if 'conclusion' in k.lower():
                remove_section = True

            if add_section:
                if not remove_section:
                    req_sections[k] = v

        req_sections = { k:v for k,v in req_sections.items() if 'reference' not in k.lower() }
        # req_sections = { k : v for k, v in req_sections.items() if not k.startswith('==>')  }
        
        return req_sections

