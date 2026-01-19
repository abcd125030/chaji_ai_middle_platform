'use client';

import TopBar from '@/components/ui/TopBar';
import { SparklesIcon, BoltIcon, CubeTransparentIcon, ArrowRightIcon, BeakerIcon, ChartBarIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const VideoPlayer = dynamic(() => import('@/components/ui/VideoPlayer'), {
  ssr: false,
});

/**
 * Enterprise homepage
 * Enterprise-grade AI platform showcase with marketing appeal
 */
export default function EnterpriseHomepage() {
  return (
    <div className="min-h-screen bg-black text-[var(--foreground)]">
      {/* Subtle background effects */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-purple-900/10 via-black to-black" />
        <div className="geometric-background" />
      </div>
      
      <TopBar />
      
      {/* Hero Section - stronger visual impact */}
      <section className="relative min-h-[90vh] flex items-center justify-center px-6">
        <div className="max-w-5xl mx-auto text-center">
          {/* Main title - bigger and more impactful */}
          <h1 className="text-[clamp(3.5rem,9vw,6.5rem)] font-bold mb-6 leading-[1.05] tracking-tight">
            <span className="block bg-gradient-to-r from-purple-400 via-pink-400 to-orange-400 bg-clip-text text-transparent">霸王茶姬</span>
            <span className="block gradient-title text-[clamp(2.5rem,7vw,5rem)]">
              Agentic Labs
            </span>
          </h1>
          
          {/* Subtitle - more attractive */}
          <p className="text-xl md:text-2xl text-[var(--foreground)] opacity-80 mb-12 max-w-3xl mx-auto leading-relaxed">
            Not just tools, but your <span className="font-semibold text-[var(--foreground)]">AI Innovation Partner</span>
            <br />
            <span className="text-lg opacity-60">Intelligent Workflows · Modular Capabilities · Enterprise Reliability</span>
          </p>
          
          {/* CTA button group */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
            <Link href="/chat">
              <button className="group relative px-8 py-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full font-semibold text-lg transition-all overflow-hidden hover:shadow-[0_20px_40px_rgba(168,85,247,0.3)]">
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700"></span>
                <span className="relative flex items-center">
                  Try Agentic
                  <ArrowRightIcon className="w-5 h-5 ml-2 transition-transform group-hover:translate-x-1" />
                </span>
              </button>
            </Link>
            <button className="px-8 py-4 text-[var(--foreground)] rounded-full font-semibold text-lg border border-[var(--border)] transition-all hover:bg-[var(--accent)] hover:border-[var(--foreground)]/40">
              Feature Overview
            </button>
          </div>
          
          {/* Trust indicators */}
          <div className="flex items-center justify-center gap-8 text-sm opacity-60">
            <span className="flex items-center gap-2">
              <BeakerIcon className="w-4 h-4" />
              Enterprise Deployment
            </span>
            <span className="flex items-center gap-2">
              <ChartBarIcon className="w-4 h-4" />
              99.9% Uptime
            </span>
            <span className="flex items-center gap-2">
              <CodeBracketIcon className="w-4 h-4" />
              Open Ecosystem
            </span>
          </div>
        </div>
      </section>

      {/* Video showcase area - more elegant presentation */}
      <section className="relative px-6 py-20">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              <span className="gradient-title">See the Future of Work</span>
            </h2>
            <p className="text-lg opacity-60">Discover in one minute how AI transforms your workflow</p>
          </div>
          
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-purple-500/20 to-pink-500/20 blur-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <div className="relative w-full max-w-[900px] mx-auto aspect-video rounded-2xl overflow-hidden border border-[var(--border)]">
              <VideoPlayer
                src={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/video/sample.m3u8`}
                controls
                playing
                muted
                width="100%"
                height="100%"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Core capabilities - redesigned */}
      <section className="relative px-6 py-20">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              <span className="gradient-title">Three Core Capabilities</span>
            </h2>
            <p className="text-lg opacity-60">Solid foundation for building enterprise-grade AI applications</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Agentic AI */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-blue-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] rounded-2xl border border-[var(--border)] hover:border-purple-500/30 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center">
                  <SparklesIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">Agentic AI</h3>
                <p className="text-[var(--foreground)] opacity-70 mb-4">
                  Intelligent workflow orchestration, automated tool chain invocation, enabling AI to truly understand and execute complex tasks
                </p>
                <ul className="space-y-2 text-sm opacity-60">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full" />
                    Automatic task decomposition
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full" />
                    Intelligent tool invocation
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-purple-400 rounded-full" />
                    Automatic result integration
                  </li>
                </ul>
              </div>
            </div>

            {/* Multi-model integration */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-pink-600/20 to-orange-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] rounded-2xl border border-[var(--border)] hover:border-pink-500/30 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-pink-500 to-pink-600 rounded-2xl flex items-center justify-center">
                  <BoltIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">Multi-Model Integration</h3>
                <p className="text-[var(--foreground)] opacity-70 mb-4">
                  Carefully selected industry-leading models, intelligent scheduling based on task characteristics, balancing performance and cost
                </p>
                <ul className="space-y-2 text-sm opacity-60">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-pink-400 rounded-full" />
                    Tongyi Qwen Series
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-pink-400 rounded-full" />
                    Claude / Kimi-K2
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-pink-400 rounded-full" />
                    Gemma 3n Private Deployment
                  </li>
                </ul>
              </div>
            </div>

            {/* One-stop platform */}
            <div className="group relative">
              <div className="absolute inset-0 bg-gradient-to-br from-orange-600/20 to-yellow-600/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="relative p-8 bg-[var(--card-bg)] rounded-2xl border border-[var(--border)] hover:border-orange-500/30 transition-all">
                <div className="w-14 h-14 mb-6 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center">
                  <CubeTransparentIcon className="w-7 h-7 text-white" />
                </div>
                <h3 className="text-2xl font-bold mb-3 gradient-title">One-Stop Platform</h3>
                <p className="text-[var(--foreground)] opacity-70 mb-4">
                  Modular architecture design, rapidly build enterprise-specific AI applications, accelerate digital transformation
                </p>
                <ul className="space-y-2 text-sm opacity-60">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-orange-400 rounded-full" />
                    Microservice Architecture
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-orange-400 rounded-full" />
                    API-First Design
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-orange-400 rounded-full" />
                    Rapid Secondary Development
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Actual capabilities showcase */}
      <section className="relative px-6 py-20 bg-[var(--background)]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">
              <span className="gradient-title">Core Capability Integration</span>
            </h2>
            <p className="text-lg opacity-60">Based on practical toolsets, providing real and usable AI capabilities for enterprises</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Intelligent conversation and generation */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-purple-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">💬</span>
                </div>
                <h3 className="text-lg font-semibold">Intelligent Conversation & Content Generation</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Multi-model intelligent conversation with context understanding and personalized responses
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• Multi-turn conversation understanding</li>
                <li>• Content creation and optimization</li>
                <li>• Multi-language translation</li>
              </ul>
            </div>

            {/* Data analysis and processing */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-pink-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-pink-500 to-pink-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">📊</span>
                </div>
                <h3 className="text-lg font-semibold">Data Analysis & Computing</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Intelligent analysis of tabular data with support for complex calculations and visualizations
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• Excel/CSV data processing</li>
                <li>• Mathematical expression calculation</li>
                <li>• Data insight extraction</li>
              </ul>
            </div>

            {/* Knowledge base management */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-blue-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">📚</span>
                </div>
                <h3 className="text-lg font-semibold">Enterprise Knowledge Base</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Vector database-driven intelligent knowledge management system
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• Document storage and retrieval</li>
                <li>• Semantic search</li>
                <li>• Knowledge Q&A</li>
              </ul>
            </div>

            {/* Information retrieval */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-green-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-green-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">🔍</span>
                </div>
                <h3 className="text-lg font-semibold">Intelligent Information Retrieval</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Real-time web search, accessing the latest industry information
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• Real-time web search</li>
                <li>• Information aggregation and analysis</li>
                <li>• Source citation tracking</li>
              </ul>
            </div>

            {/* Report generation */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-orange-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-orange-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">📄</span>
                </div>
                <h3 className="text-lg font-semibold">Intelligent Report Generation</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Automated generation of professional reports and documents
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• Structured report output</li>
                <li>• Data integration and analysis</li>
                <li>• Automatic format optimization</li>
              </ul>
            </div>

            {/* Task planning */}
            <div className="p-6 bg-[var(--card-bg)] rounded-xl border border-[var(--border)] hover:border-indigo-500/30 transition-all">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-lg flex items-center justify-center">
                  <span className="text-white text-lg">✅</span>
                </div>
                <h3 className="text-lg font-semibold">Intelligent Task Planning</h3>
              </div>
              <p className="text-sm opacity-70 mb-3">
                Complex task automatic decomposition and execution tracking
              </p>
              <ul className="text-sm opacity-60 space-y-1">
                <li>• TODO list generation</li>
                <li>• Task dependency management</li>
                <li>• Automatic progress tracking</li>
              </ul>
            </div>
          </div>

          {/* Bottom description */}
          <div className="mt-12 text-center">
            <p className="text-sm opacity-50">
              Based on Agentic AI architecture, all capabilities can be used in combination, automatically orchestrating complex workflows
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative px-6 py-20">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-6">
            Ready to start the <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">AI-Driven Future</span>?
          </h2>
          <p className="text-lg opacity-60 mb-10">
            Explore the unlimited possibilities of AI within enterprises together
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/chat">
              <button className="group relative px-10 py-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full font-semibold text-lg transition-all overflow-hidden hover:shadow-[0_20px_40px_rgba(168,85,247,0.3)]">
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent -translate-x-full group-hover:translate-x-full transition-transform duration-700"></span>
                <span className="relative">Get Started</span>
              </button>
            </Link>
            <button className="px-10 py-4 text-[var(--foreground)] rounded-full font-semibold text-lg border border-[var(--border)] transition-all hover:bg-[var(--accent)] hover:border-[var(--foreground)]/40">
              Technical Documentation
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}