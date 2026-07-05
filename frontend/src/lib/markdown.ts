import { marked } from 'marked'
import DOMPurify from 'dompurify'

export function renderMarkdown(source: string): string {
  const raw = marked.parse(source, { async: false }) as string
  return DOMPurify.sanitize(raw)
}

export function stripFrontmatter(source: string): { body: string; frontmatter: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!match) return { frontmatter: '', body: source }
  return { frontmatter: match[1], body: match[2] }
}
