import Link from 'next/link';

export default function DocsPage() {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Documentation Center</h1>
        <p className="text-xl text-gray-600">
          Welcome to the Enterprise AI Platform Documentation Center, containing comprehensive user guides and development documentation.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* 快速开始 */}
        <Link href="/docs/getting-started" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                🚀
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">Quick Start</h3>
            </div>
            <p className="text-gray-600">Learn how to quickly get started with the AI platform</p>
          </div>
        </Link>

        {/* API 文档 */}
        <Link href="/docs/api" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center mr-3">
                📋
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">API Documentation</h3>
            </div>
            <p className="text-gray-600">Complete API interface documentation and call examples</p>
          </div>
        </Link>

        {/* 架构设计 */}
        <Link href="/docs/architecture" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
                🏗️
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">Architecture Design</h3>
            </div>
            <p className="text-gray-600">Understand system architecture and design principles</p>
          </div>
        </Link>

        {/* 开发指南 */}
        <Link href="/docs/development" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-yellow-100 rounded-lg flex items-center justify-center mr-3">
                💻
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">Development Guide</h3>
            </div>
            <p className="text-gray-600">Development environment setup and coding standards</p>
          </div>
        </Link>

        {/* 部署指南 */}
        <Link href="/docs/deployment" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-red-100 rounded-lg flex items-center justify-center mr-3">
                🚁
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">Deployment Guide</h3>
            </div>
            <p className="text-gray-600">Production environment deployment and operations guide</p>
          </div>
        </Link>

        {/* 故障排除 */}
        <Link href="/docs/troubleshooting" className="group">
          <div className="border rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center mb-3">
              <div className="w-8 h-8 bg-orange-100 rounded-lg flex items-center justify-center mr-3">
                🔧
              </div>
              <h3 className="text-lg font-semibold group-hover:text-blue-600">Troubleshooting</h3>
            </div>
            <p className="text-gray-600">Common issues and solutions</p>
          </div>
        </Link>
      </div>
    </div>
  );
}