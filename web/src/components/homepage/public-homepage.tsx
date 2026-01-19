'use client';

import Link from 'next/link';
import TopBar from '@/components/ui/TopBar';
import { ArrowRightIcon, SparklesIcon, BookOpenIcon, LightBulbIcon } from '@heroicons/react/24/outline';

/**
 * 公开版首页
 * 聚焦产品价值：个人AI助手的培育和成长
 */
export default function PublicHomepage() {
  return (
    <div className="min-h-screen bg-black text-[var(--foreground)]">
      {/* 细腻的背景 */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-900/20 via-black to-black" />
      </div>

      <TopBar />

      {/* Hero Section - 产品价值导向 */}
      <section className="relative min-h-[90vh] flex items-center justify-center px-6">
        <div className="max-w-5xl mx-auto text-center">
          {/* 主标题 - 聚焦用户价值 */}
          <h1 className="text-[clamp(3rem,8vw,5.5rem)] font-bold mb-6 leading-[1.1] tracking-tight">
            <span className="block gradient-title">
              Your AI That
            </span>
            <span className="block bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              Grows With You
            </span>
          </h1>

          {/* 副标题 - 产品核心价值 */}
          <p className="text-xl md:text-2xl text-gray-300 mb-12 max-w-2xl mx-auto leading-relaxed">
            Not just another chatbot. Build your personal AI assistant that learns from your knowledge, 
            remembers your preferences, and evolves with every interaction.
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-16">
            <Link href="/chat">
              <button className="group px-8 py-4 bg-[var(--foreground)] text-black rounded-full font-semibold text-lg transition-all hover:scale-105 hover:shadow-[0_20px_40px_rgba(255,255,255,0.15)]">
                <span className="flex items-center">
                  Start Training Your AI
                  <ArrowRightIcon className="w-5 h-5 ml-2 transition-transform group-hover:translate-x-1" />
                </span>
              </button>
            </Link>
            
            <Link href="#demo">
              <button className="px-8 py-4 text-[var(--foreground)] rounded-full font-semibold text-lg border border-[var(--border)] transition-all hover:bg-[var(--accent)] hover:border-[var(--foreground)]/40">
                See It In Action
              </button>
            </Link>
          </div>

          {/* 用户数据 */}
          <div className="inline-flex items-center gap-6 text-sm text-gray-400">
            <div className="flex -space-x-2">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 border-2 border-black" />
              ))}
            </div>
            <span>Join 10,000+ professionals building their AI assistants</span>
          </div>
        </div>
      </section>

      {/* 产品核心功能 - 用故事讲述 */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">
              An AI That Actually <span className="text-purple-400">Understands</span> You
            </h2>
            <p className="text-xl text-gray-400">
              Every conversation makes it smarter. Every document makes it wiser.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Chat - 对话产品 */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-purple-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] backdrop-blur rounded-2xl border border-[var(--border)] hover:border-[var(--foreground)]/20 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center">
                  <SparklesIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">Conversational AI</h3>
                <p className="text-gray-400 mb-4">
                  More than Q&A. Your AI remembers context, understands nuance, and provides thoughtful responses tailored to your communication style.
                </p>
                <Link href="/chat" className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-2 font-medium">
                  Start chatting <ArrowRightIcon className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Knowledge Base - 知识管理 */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-pink-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] backdrop-blur rounded-2xl border border-[var(--border)] hover:border-[var(--foreground)]/20 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center">
                  <BookOpenIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">Living Knowledge</h3>
                <p className="text-gray-400 mb-4">
                  Upload documents, notes, and data. Your AI instantly learns and can recall any detail when you need it. Your second brain, but better.
                </p>
                <Link href="/knowledge" className="text-purple-400 hover:text-purple-300 inline-flex items-center gap-2 font-medium">
                  Build knowledge <ArrowRightIcon className="w-4 h-4" />
                </Link>
              </div>
            </div>

            {/* Pagtive - 项目管理 */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-green-600/20 to-emerald-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] backdrop-blur rounded-2xl border border-[var(--border)] hover:border-[var(--foreground)]/20 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center">
                  <LightBulbIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">Project Intelligence</h3>
                <p className="text-gray-400 mb-4">
                  Manage projects with an AI that learns your workflow, automates routine tasks, and provides insights you didn&apos;t know you needed.
                </p>
                <Link href="/pagtive" className="text-green-400 hover:text-green-300 inline-flex items-center gap-2 font-medium">
                  Explore Pagtive <ArrowRightIcon className="w-4 h-4" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* AI成长展示 */}
      <section className="py-24 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <h2 className="text-4xl md:text-5xl font-bold mb-6">
                Watch Your AI <span className="text-gradient bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">Evolve</span>
              </h2>
              <p className="text-xl text-gray-300 mb-8">
                Every interaction teaches your AI something new. Over time, it becomes an extension of your thinking.
              </p>

              {/* 成长阶段 */}
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                    <span className="text-blue-400 font-bold">1</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-1 gradient-title">Day 1: Basic Assistant</h3>
                    <p className="text-gray-400">Answers questions, helps with tasks, learns your name and preferences</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                    <span className="text-purple-400 font-bold">7</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-1 gradient-title">Week 1: Context Aware</h3>
                    <p className="text-gray-400">Remembers past conversations, understands your projects, anticipates needs</p>
                  </div>
                </div>

                <div className="flex gap-4">
                  <div className="w-12 h-12 rounded-full bg-pink-500/20 flex items-center justify-center flex-shrink-0">
                    <span className="text-pink-400 font-bold">30</span>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold mb-1 gradient-title">Month 1: True Partner</h3>
                    <p className="text-gray-400">Proactively suggests ideas, connects dots across projects, thinks like you do</p>
                  </div>
                </div>
              </div>
            </div>

            {/* 视觉展示 */}
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-pink-500/10 blur-3xl" />
              <div className="relative bg-black/40 backdrop-blur rounded-2xl border border-white/10 p-8">
                <div className="space-y-4">
                  {/* 模拟对话展示 */}
                  <div className="p-4 bg-white/5 rounded-xl">
                    <p className="text-sm text-gray-400 mb-2">You:</p>
                    <p>&ldquo;What was that idea we discussed last Tuesday about the marketing campaign?&rdquo;</p>
                  </div>
                  <div className="p-4 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-xl border border-purple-500/20">
                    <p className="text-sm text-purple-400 mb-2">Your AI:</p>
                    <p>&ldquo;You mentioned using influencer partnerships for the Q2 campaign. I&apos;ve also analyzed your uploaded competitor reports - their approach focuses on micro-influencers with 10K-50K followers. Based on your budget constraints we discussed, I&apos;d recommend starting with 5-10 micro-influencers in the tech space.&rdquo;</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 使用场景 */}
      <section className="py-24 px-6 border-t border-white/5">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold mb-4">
              Built for How You <span className="text-blue-400">Actually Work</span>
            </h2>
            <p className="text-xl text-gray-400">
              Real professionals. Real results. Every day.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { role: "Product Manager", task: "Synthesize user feedback from 100+ interviews in seconds" },
              { role: "Researcher", task: "Connect findings across thousands of papers and documents" },
              { role: "Consultant", task: "Generate insights from client data without manual analysis" },
              { role: "Entrepreneur", task: "Keep track of everything while focusing on what matters" },
              { role: "Developer", task: "Document and recall technical decisions instantly" },
              { role: "Marketer", task: "Create consistent content that matches your brand voice" },
              { role: "Designer", task: "Maintain design systems and recall past decisions" },
              { role: "Analyst", task: "Surface patterns in data you didn't know existed" },
            ].map((item, i) => (
              <div key={i} className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-[var(--foreground)]/20 transition-all">
                <h3 className="font-semibold mb-2 gradient-title">{item.role}</h3>
                <p className="text-sm text-gray-400">{item.task}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 信任和安全 */}
      <section className="py-24 px-6 border-t border-white/5">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Your Data. Your AI. <span className="text-green-400">Your Control.</span>
          </h2>
          <p className="text-xl text-gray-300 mb-12">
            End-to-end encryption. No training on your data. Delete anytime.
          </p>

          <div className="grid md:grid-cols-3 gap-8 mb-12">
            <div>
              <div className="text-3xl font-bold text-green-400 mb-2">Private</div>
              <p className="text-gray-400">Your conversations and data stay yours</p>
            </div>
            <div>
              <div className="text-3xl font-bold text-blue-400 mb-2">Secure</div>
              <p className="text-gray-400">Enterprise-grade security, always</p>
            </div>
            <div>
              <div className="text-3xl font-bold text-purple-400 mb-2">Compliant</div>
              <p className="text-gray-400">SOC2, GDPR, and HIPAA ready</p>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-6 border-t border-white/5">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">
            Start Building Your <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">Personal AI</span> Today
          </h2>
          <p className="text-xl text-gray-300 mb-12">
            Free to start. No credit card required. Your AI journey begins now.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/chat">
              <button className="px-10 py-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-full font-semibold text-lg transition-all hover:scale-105 hover:shadow-[0_20px_40px_rgba(99,102,241,0.3)]">
                Get Started Free
              </button>
            </Link>
            
            <Link href="/demo">
              <button className="px-10 py-4 text-white rounded-full font-semibold text-lg border border-white/20 transition-all hover:bg-white/5 hover:border-white/40">
                Book a Demo
              </button>
            </Link>
          </div>
          
          <p className="mt-8 text-sm text-gray-500">
            ✓ Free forever for personal use &nbsp;&nbsp; ✓ Upgrade anytime &nbsp;&nbsp; ✓ Cancel anytime
          </p>
        </div>
      </section>
    </div>
  );
}