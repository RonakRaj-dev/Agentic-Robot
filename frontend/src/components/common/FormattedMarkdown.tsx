import React from 'react';

interface FormattedMarkdownProps {
  content: string;
  className?: string;
}

export const FormattedMarkdown: React.FC<FormattedMarkdownProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // Clean out any model thinking process (<think>...</think>) before rendering
  const sanitizedContent = content
    .replace(/<think>[\s\S]*?<\/think>/gi, '')
    .replace(/^<think>[\s\S]*?(?=\n#|\n\*\*|\n[A-Z]|\n\n[A-Z]|$)/gi, '')
    .replace(/^Here's a thinking process:[\s\S]*?(?=\n#|\n\*\*|\n[A-Z]|\n\n[A-Z]|$)/gi, '')
    .trim();

  if (!sanitizedContent) return null;

  // Function to parse inline formatting like **bold**, *italic*, and `code`
  const parseInline = (text: string): React.ReactNode[] => {
    // Regex matching **bold**, *italic*, `code`
    const parts: React.ReactNode[] = [];
    let remaining = text;
    let keyIdx = 0;

    while (remaining.length > 0) {
      // Match bold **text**
      const boldMatch = remaining.match(/\*\*(.*?)\*\*/);
      // Match italic *text*
      const italicMatch = remaining.match(/\*(.*?)\*/);
      // Match code `text`
      const codeMatch = remaining.match(/`(.*?)`/);

      // Find which match comes first
      const matches = [
        boldMatch ? { type: 'bold', index: boldMatch.index!, match: boldMatch } : null,
        italicMatch ? { type: 'italic', index: italicMatch.index!, match: italicMatch } : null,
        codeMatch ? { type: 'code', index: codeMatch.index!, match: codeMatch } : null,
      ].filter(Boolean).sort((a, b) => a!.index - b!.index);

      if (matches.length === 0) {
        parts.push(remaining);
        break;
      }

      const first = matches[0]!;
      if (first.index > 0) {
        parts.push(remaining.substring(0, first.index));
      }

      const raw = first.match[0];
      const innerText = first.match[1];

      if (first.type === 'bold') {
        parts.push(<strong key={keyIdx++} className="font-extrabold text-[#1c1b1b]">{innerText}</strong>);
      } else if (first.type === 'italic') {
        parts.push(<em key={keyIdx++} className="italic">{innerText}</em>);
      } else if (first.type === 'code') {
        parts.push(<code key={keyIdx++} className="bg-[#f0eded] px-1.5 py-0.5 rounded font-mono text-xs text-[#bc000a] border border-[#1c1b1b]/20">{innerText}</code>);
      }

      remaining = remaining.substring(first.index + raw.length);
    }

    return parts;
  };

  // Helper to parse Markdown tables
  const renderTable = (lines: string[], tableKey: number) => {
    if (lines.length < 2) return null;
    const parseRow = (line: string) =>
      line.split('|').map((cell) => cell.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);


    const headerRow = parseRow(lines[0]);
    const bodyRows = lines.slice(2).map(parseRow);

    return (
      <div key={tableKey} className="my-4 overflow-x-auto">
        <table className="w-full text-left border-collapse border-2 border-[#1c1b1b] text-sm bg-white shadow-[3px_3px_0px_#1c1b1b]">
          <thead>
            <tr className="bg-[#fecb00] border-b-2 border-[#1c1b1b]">
              {headerRow.map((col, idx) => (
                <th key={idx} className="p-2.5 font-pixel text-xs font-bold border-r border-[#1c1b1b] text-[#1c1b1b] uppercase">
                  {parseInline(col)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {bodyRows.map((row, rIdx) => (
              <tr key={rIdx} className={rIdx % 2 === 0 ? 'bg-white' : 'bg-[#f0eded]/50'}>
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="p-2.5 border-t border-r border-[#1c1b1b] font-body text-xs font-semibold text-[#1c1b1b]">
                    {parseInline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const rawLines = sanitizedContent.split('\n');
  const elements: React.ReactNode[] = [];
  let idx = 0;
  let i = 0;

  while (i < rawLines.length) {
    const line = rawLines[i].trim();

    // 1. Horizontal Rule ---
    if (line === '---' || line === '***' || line === '___') {
      elements.push(<hr key={idx++} className="my-4 border-t-2 border-[#1c1b1b]" />);
      i++;
      continue;
    }

    // 2. Table Detection (| Header | Header |)
    if (line.startsWith('|') && line.endsWith('|')) {
      const tableLines: string[] = [];
      while (i < rawLines.length && rawLines[i].trim().startsWith('|')) {
        tableLines.push(rawLines[i].trim());
        i++;
      }
      elements.push(renderTable(tableLines, idx++));
      continue;
    }

    // 3. Headers (# ## ###)
    if (line.startsWith('#')) {
      const level = line.match(/^#+/)?.[0].length || 1;
      const text = line.replace(/^#+\s*/, '');
      const parsedText = parseInline(text);

      if (level === 1) {
        elements.push(
          <h1 key={idx++} className="font-headline font-bold text-2xl text-[#1c1b1b] mt-4 mb-2 border-b-2 border-[#1c1b1b] pb-1">
            {parsedText}
          </h1>
        );
      } else if (level === 2) {
        elements.push(
          <h2 key={idx++} className="font-headline font-bold text-xl text-[#bc000a] mt-4 mb-2 flex items-center gap-1.5">
            {parsedText}
          </h2>
        );
      } else {
        elements.push(
          <h3 key={idx++} className="font-headline font-bold text-lg text-[#1c1b1b] mt-3 mb-1">
            {parsedText}
          </h3>
        );
      }
      i++;
      continue;
    }

    // 4. Bullet & Numbered Lists
    const isBullet = line.startsWith('- ') || line.startsWith('* ');
    const isNumber = /^\d+\.\s/.test(line);

    if (isBullet || isNumber) {
      const listItems: { text: string; isNumber: boolean; isSubItem: boolean }[] = [];
      
      while (i < rawLines.length) {
        const rawL = rawLines[i];
        const trimmedL = rawL.trim();
        const indent = rawL.search(/\S/);
        
        const bMatch = trimmedL.startsWith('- ') || trimmedL.startsWith('* ');
        const nMatch = /^\d+\.\s/.test(trimmedL);
        
        if (bMatch || nMatch) {
          const text = trimmedL.replace(/^[-*]\s+|\d+\.\s+/, '');
          listItems.push({ text, isNumber: nMatch, isSubItem: indent >= 2 });
          i++;
        } else if (indent > 0 && trimmedL.length > 0) {
          // Continuation line of list item
          if (listItems.length > 0) {
            listItems[listItems.length - 1].text += ' ' + trimmedL;
          }
          i++;
        } else {
          break;
        }
      }

      elements.push(
        <div key={idx++} className="my-2 space-y-1.5 pl-2">
          {listItems.map((item, lIdx) => (
            <div
              key={lIdx}
              className={`flex items-start gap-2 text-sm leading-relaxed font-medium text-[#1c1b1b] ${
                item.isSubItem ? 'ml-5 text-xs text-[#494454]' : ''
              }`}
            >
              <span className="font-pixel text-xs text-[#bc000a] shrink-0 mt-0.5">
                {item.isNumber ? `${lIdx + 1}.` : '•'}
              </span>
              <div className="flex-1">{parseInline(item.text)}</div>
            </div>
          ))}
        </div>
      );
      continue;
    }

    // 5. Regular Paragraph
    if (line.length > 0) {
      elements.push(
        <p key={idx++} className="text-sm font-semibold text-[#1c1b1b] leading-relaxed my-2 whitespace-pre-wrap">
          {parseInline(line)}
        </p>
      );
    }

    i++;
  }

  return <div className={`space-y-1 text-left ${className}`}>{elements}</div>;
};
