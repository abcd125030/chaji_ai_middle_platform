import { ReactNode } from 'react';

// MDX 自定义组件
const MDXComponents = {
  // 标题组件
  h1: ({ children, ...props }: { children: ReactNode }) => (
    <h1 
      className="text-3xl font-bold text-gray-900 mb-6 pb-3 border-b border-gray-200" 
      {...props}
    >
      {children}
    </h1>
  ),
  
  h2: ({ children, ...props }: { children: ReactNode }) => (
    <h2 
      className="text-2xl font-semibold text-gray-900 mt-8 mb-4" 
      {...props}
    >
      {children}
    </h2>
  ),
  
  h3: ({ children, ...props }: { children: ReactNode }) => (
    <h3 
      className="text-xl font-semibold text-gray-900 mt-6 mb-3" 
      {...props}
    >
      {children}
    </h3>
  ),
  
  h4: ({ children, ...props }: { children: ReactNode }) => (
    <h4 
      className="text-lg font-medium text-gray-900 mt-4 mb-2" 
      {...props}
    >
      {children}
    </h4>
  ),

  // 段落和文本
  p: ({ children, ...props }: { children: ReactNode }) => (
    <p 
      className="text-gray-700 leading-relaxed mb-4" 
      {...props}
    >
      {children}
    </p>
  ),

  // 列表
  ul: ({ children, ...props }: { children: ReactNode }) => (
    <ul 
      className="list-disc list-inside mb-4 space-y-1 text-gray-700" 
      {...props}
    >
      {children}
    </ul>
  ),
  
  ol: ({ children, ...props }: { children: ReactNode }) => (
    <ol 
      className="list-decimal list-inside mb-4 space-y-1 text-gray-700" 
      {...props}
    >
      {children}
    </ol>
  ),
  
  li: ({ children, ...props }: { children: ReactNode }) => (
    <li 
      className="mb-1" 
      {...props}
    >
      {children}
    </li>
  ),

  // 链接
  a: ({ children, href, ...props }: { children: ReactNode; href?: string }) => (
    <a 
      href={href}
      className="text-blue-600 hover:text-blue-800 underline decoration-blue-200 hover:decoration-blue-400 transition-colors"
      {...props}
    >
      {children}
    </a>
  ),

  // 代码块
  code: ({ children, className, ...props }: { children: ReactNode; className?: string }) => {
    const isInline = !className;
    
    if (isInline) {
      return (
        <code 
          className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" 
          {...props}
        >
          {children}
        </code>
      );
    }
    
    return (
      <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto mb-4">
        <code className={className} {...props}>
          {children}
        </code>
      </pre>
    );
  },

  pre: ({ children }: { children: ReactNode }) => (
    <div className="mb-4">
      {children}
    </div>
  ),

  // 引用块
  blockquote: ({ children, ...props }: { children: ReactNode }) => (
    <blockquote 
      className="border-l-4 border-blue-200 pl-4 py-2 my-4 bg-blue-50 text-gray-700 italic" 
      {...props}
    >
      {children}
    </blockquote>
  ),

  // 表格
  table: ({ children, ...props }: { children: ReactNode }) => (
    <div className="overflow-x-auto mb-4">
      <table 
        className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg" 
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  
  thead: ({ children, ...props }: { children: ReactNode }) => (
    <thead 
      className="bg-gray-50" 
      {...props}
    >
      {children}
    </thead>
  ),
  
  tbody: ({ children, ...props }: { children: ReactNode }) => (
    <tbody 
      className="bg-white divide-y divide-gray-200" 
      {...props}
    >
      {children}
    </tbody>
  ),
  
  th: ({ children, ...props }: { children: ReactNode }) => (
    <th 
      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" 
      {...props}
    >
      {children}
    </th>
  ),
  
  td: ({ children, ...props }: { children: ReactNode }) => (
    <td 
      className="px-6 py-4 whitespace-nowrap text-sm text-gray-900" 
      {...props}
    >
      {children}
    </td>
  ),

  // 分隔线
  hr: (props: React.HTMLAttributes<HTMLHRElement>) => (
    <hr 
      className="my-8 border-t border-gray-200" 
      {...props}
    />
  ),

  // 强调
  strong: ({ children, ...props }: { children: ReactNode }) => (
    <strong 
      className="font-semibold text-gray-900" 
      {...props}
    >
      {children}
    </strong>
  ),
  
  em: ({ children, ...props }: { children: ReactNode }) => (
    <em 
      className="italic text-gray-700" 
      {...props}
    >
      {children}
    </em>
  ),

  // 图片
  img: ({ src, alt, ...props }: { src?: string; alt?: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img 
      src={src}
      alt={alt}
      className="max-w-full h-auto rounded-lg shadow-sm my-4"
      {...props}
    />
  ),
};

export default MDXComponents;