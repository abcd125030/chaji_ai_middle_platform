import type { MDXComponents } from 'mdx/types';
import CustomMDXComponents from '@/components/docs/MDXComponents';

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    ...CustomMDXComponents,
    ...components,
  };
}