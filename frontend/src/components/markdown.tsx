import Markdown from 'react-markdown'
import { cn } from '@/lib/utils'

// Typography for agent-written Markdown, without a prose plugin: descendant selectors only.
const prose = [
  'text-[14px] leading-relaxed break-words',
  '[&_h1]:mt-5 [&_h1]:mb-2 [&_h1]:text-[19px] [&_h1]:font-semibold [&_h1]:tracking-tight',
  '[&_h2]:mt-5 [&_h2]:mb-2 [&_h2]:text-[17px] [&_h2]:font-semibold [&_h2]:tracking-tight',
  '[&_h3]:mt-4 [&_h3]:mb-1.5 [&_h3]:text-[15px] [&_h3]:font-semibold',
  '[&_h4]:mt-3 [&_h4]:mb-1 [&_h4]:font-semibold',
  '[&>:first-child]:mt-0 [&_p]:my-2.5',
  '[&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1',
  '[&_a]:text-live [&_a]:underline [&_a]:underline-offset-2',
  '[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground',
  '[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-px [&_code]:font-mono [&_code]:text-[0.9em]',
  '[&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-[10px] [&_pre]:bg-muted [&_pre]:p-3',
  '[&_pre_code]:bg-transparent [&_pre_code]:p-0',
  '[&_hr]:my-5 [&_strong]:font-semibold',
].join(' ')

/**
 * Markdown written by the agent. Raw HTML is dropped (`skipHtml`), never rendered: the text
 * comes from the genome, and react-markdown already neutralises unsafe link protocols.
 */
export function AgentMarkdown({ text, className, lang }: { text: string; className?: string; lang?: string }) {
  return (
    <div className={cn(prose, className)} lang={lang}>
      <Markdown skipHtml>{text}</Markdown>
    </div>
  )
}
