/**
 * Utility to strip Markdown formatting, tables, symbols, and non-speakable characters
 * from text before sending it to Web Speech API SpeechSynthesisUtterance.
 */
export function cleanTextForSpeech(text: string): string {
  if (!text) return '';

  let clean = text;

  // 1. Convert Markdown tables (| Col 1 | Col 2 |) into natural sentence strings
  clean = clean.replace(/\|[^\n]+\|/g, (tableRow) => {
    if (tableRow.includes('---')) return '';
    const cells = tableRow
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    return cells.join(', ');
  });

  // 2. Remove horizontal rules (---, ***, ___)
  clean = clean.replace(/^(?:---|[*]{3}|_{3})$/gm, '');

  // 3. Remove Markdown headings (# ## ### ####)
  clean = clean.replace(/^#{1,6}\s+/gm, '');

  // 4. Remove bold (**text** or __text__) and italic (*text* or _text_) markup
  clean = clean.replace(/\*\*(.*?)\*\*/g, '$1');
  clean = clean.replace(/__(.*?)__/g, '$1');
  clean = clean.replace(/\*(.*?)\*/g, '$1');
  clean = clean.replace(/_(.*?)_/g, '$1');

  // 5. Remove inline code blocks (`code`)
  clean = clean.replace(/`(.*?)`/g, '$1');

  // 6. Remove bullet markers (- item, * item) and list numbers (1. item, 2. item)
  clean = clean.replace(/^[-*]\s+/gm, '');
  clean = clean.replace(/^\d+\.\s+/gm, '');

  // 7. Strip Emojis and decorative unicode symbols (e.g. 🌟, 🚀, 🤖, 1️⃣, 2️⃣, etc.)
  clean = clean.replace(
    /[\u{1F300}-\u{1F9FF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{1F1E0}-\u{1F1FF}]|[\u{200D}]|[\u{FE0F}]|[\u{00A9}\u{00AE}\u{2122}]|[\u{203C}\u{2049}\u{25AA}\u{25AB}\u{25B6}\u{25C0}\u{25FB}-\u{25FE}]|[\u{0030}-\u{0039}]\u{FE0F}?\u{20E3}/gu,
    ''
  );

  // 8. Replace leftover brackets or markdown links [Text](url)
  clean = clean.replace(/\[(.*?)\]\(.*?\)/g, '$1');

  // 9. Normalize multiple newlines, extra spaces, and orphaned symbols into smooth pauses
  clean = clean.replace(/[\r\n]+/g, '. ');
  clean = clean.replace(/\s+/g, ' ');
  clean = clean.replace(/\.\s*\./g, '.');

  return clean.trim();
}
