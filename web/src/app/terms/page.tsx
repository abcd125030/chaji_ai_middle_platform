import React from 'react';
import { siteConfig } from '@/lib/site-config';

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="container mx-auto px-4 py-12">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-4xl font-bold mb-8 text-center">服务条款</h1>
          
          <div className="space-y-6 text-gray-700 dark:text-gray-300">
            <section>
              <h2 className="text-2xl font-semibold mb-3">1. 总则</h2>
              <p>
                欢迎使用 {siteConfig.fullName}（以下简称“本平台”）。本平台为内部AI大语言模型应用平台，旨在提供高效的AI服务以支持内部业务需求。在您使用本平台前，请仔细阅读并理解本服务条款（以下简称“本条款”）的所有内容。您通过飞书账号登录并使用本平台的行为，即表示您已阅读、理解并同意接受本条款的全部内容。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">2. 服务内容</h2>
              <p>
                本平台基于AI大语言模型，提供包括但不限于企业知识库问答、聊天对话、定制化服务（如舆情分析、绩效评估、PDF文档处理）等功能。所有服务均通过内部网络提供，并与公司现有的飞书认证体系集成。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">3. 用户账户与认证</h2>
              <p>
                本平台仅限内部员工使用。用户需通过公司指定的飞书账号进行OAuth2.0授权登录。您有责任妥善保管您的飞书账号信息，并对通过您账户进行的所有活动负责。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">4. 用户行为规范</h2>
              <p>
                您在使用本平台时，必须遵守国家法律法规及公司内部规章制度。您承诺不会利用本平台进行任何违法、侵权或不正当的活动，包括但不限于：
              </p>
              <ul className="list-disc list-inside pl-4 mt-2 space-y-1">
                <li>上传、分享或处理任何包含敏感、机密或违反公司规定的信息。</li>
                <li>试图破解、反向工程或以其他方式获取本平台的核心技术或源代码。</li>
                <li>进行任何可能影响平台正常运行、或对其他用户造成干扰的行为。</li>
                <li>将平台提供的服务用于任何商业目的或提供给未经授权的第三方。</li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">5. 数据与知识产权</h2>
              <p>
                您在使用本平台过程中输入的数据（如查询、上传的文件等）以及平台生成的输出内容，其知识产权归属遵循公司相关规定。本平台本身的技术、代码、界面设计等所有知识产权归我方所有。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">6. 免责声明</h2>
              <p>
                本平台提供的AI生成内容可能存在不准确或不完整之处，仅供参考，不应作为决策的唯一依据。对于因使用或依赖本平台服务而可能导致的任何直接或间接损失，本平台不承担任何责任。服务可能会因系统维护、升级或不可抗力等原因中断，我们将尽力减少影响，但不保证服务的绝对连续性。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">7. 条款修订</h2>
              <p>
                我们保留随时修改本条款的权利。任何修改将在平台公示，并自公示之日起生效。若您在条款修改后继续使用本平台，即视为您已接受修改后的条款。
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold mb-3">8. 联系我们</h2>
              <p>
                如果您对本条款有任何疑问，请通过内部渠道联系AI实验室团队。
              </p>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}