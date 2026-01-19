import React from 'react';
import { siteConfig } from '@/lib/site-config';

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold mb-8 text-center">隐私政策</h1>

          <div className="space-y-6 text-gray-700 dark:text-gray-300">
            <section>
              <h2 className="text-2xl font-semibold mb-3">1. 引言</h2>
              <p>
                {siteConfig.fullName}（&ldquo;本平台&rdquo;）深知隐私对您的重要性，并会尊重您的隐私。本隐私政策（&ldquo;本政策&rdquo;）旨在说明我们如何收集、使用、存储和保护您的个人信息。本政策适用于所有通过本平台提供的服务。请您在使用本平台服务前，仔细阅读并充分理解本政策。您使用或继续使用我们提供的服务，即意味着您同意我们按照本政策处理您的相关信息。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">2. 我们收集的信息</h2>
              <p>
                作为内部服务平台，我们仅收集为实现产品功能所必需的最基本信息：
              </p>
              <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                <li>
                  <strong>身份认证信息：</strong>当您通过飞书登录时，我们会根据飞书开放平台的授权，获取您的基本身份信息（如姓名、部门、头像等），用于创建和管理您的内部账户。我们不会存储您的飞书密码。
                </li>
                <li>
                  <strong>使用数据：</strong>我们会记录您与本平台交互的信息，例如您提交的查询、上传的文档（如PDF）、创建的会话历史以及与AI模型的交互记录。这些信息用于提供服务、功能优化和问题排查。
                </li>
                <li>
                  <strong>日志信息：</strong>为了保障服务的正常运行和安全，我们会自动收集技术性的日志信息，包括API请求/响应、调用耗时、IP地址及错误日志等。
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">3. 我们如何使用信息</h2>
              <p>
                我们严格遵守内部数据安全规定，将收集的信息用于以下目的：
              </p>
              <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                <li>
                  <strong>提供和维护服务：</strong>用于验证您的身份，为您提供个性化的AI服务，并确保平台的正常运行。
                </li>
                <li>
                  <strong>服务优化与研发：</strong>分析使用数据以了解用户需求，改进现有功能，并为开发新功能提供支持。所有分析均在匿名化或假名化后进行。
                </li>
                <li>
                  <strong>安全保障：</strong>用于监控和防止欺诈、滥用或其他有害活动，保护公司、您及其他用户的合法权益。
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">4. 信息的存储与保护</h2>
              <p>
                我们采取了行业标准的安全技术和管理措施来保护您的信息，防止数据丢失、被滥用、未经授权访问或泄露。
              </p>
              <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                <li>
                  <strong>数据存储：</strong>所有数据均存储在公司内部的服务器和数据库中（如PostgreSQL），并受到严格的访问控制。
                </li>
                <li>
                  <strong>安全措施：</strong>我们采用JWT无状态认证、HTTPS加密传输、数据库连接池管理、多租户数据隔离等机制来保障数据安全。
                </li>
                <li>
                  <strong>数据保留：</strong>我们仅在实现本政策所述目的所必需的期限内保留您的个人信息，除非需要延长保留期或受到法律的允许。
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">5. 信息的共享与披露</h2>
              <p>
                我们不会与任何公司外部的第三方共享您的个人信息，除非：
              </p>
              <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                <li>获得您的明确同意。</li>
                <li>根据法律法规或行政、司法机构的强制性要求。</li>
                <li>在法律法规允许的范围内，为保护公司、您或其他用户的利益、财产或安全免遭损害而有必要提供。</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">6. 政策的更新</h2>
              <p>
                我们可能会适时对本隐私政策进行修订。当政策发生变更时，我们会在平台内通过适当方式通知您。请您定期查看本政策，以便及时了解相关更新。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">7. 联系我们</h2>
              <p>
                如果您对本隐私政策有任何疑问、意见或建议，请通过内部渠道与AI实验室团队联系。
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}