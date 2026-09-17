import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Props = {
  children: string;
};

export function MarkdownContent({ children }: Props) {
  const normalized = children.replace(/\*\*([^*\n]+?)\s+\*\*/g, "**$1**");

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      skipHtml
      components={{
        a: (props) => <a {...props} target="_blank" rel="noreferrer" />,
      }}
    >
      {normalized}
    </ReactMarkdown>
  );
}
