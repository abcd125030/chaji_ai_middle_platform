import { HomepageRouter } from '@/components/homepage';

/**
 * 应用首页
 * 通过 HomepageRouter 根据配置动态加载对应的首页组件
 */
export default function HomePage() {
  return <HomepageRouter />;
}