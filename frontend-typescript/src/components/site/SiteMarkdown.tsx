import ReactMarkdown, { type Components } from "react-markdown";
import { Link } from "react-router-dom";

const components: Components = {
  a: ({ href = "", children, ...props }) => {
    if (href.startsWith("/") || href.startsWith("#")) {
      return (
        <Link to={href} {...props}>
          {children}
        </Link>
      );
    }
    return (
      <a href={href} rel="noopener noreferrer" target="_blank" {...props}>
        {children}
      </a>
    );
  },
};

export function SiteMarkdown({ children }: { children: string }) {
  return <ReactMarkdown components={components}>{children}</ReactMarkdown>;
}
