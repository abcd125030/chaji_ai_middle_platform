import {
  CloudIcon,
  ShoppingBagIcon,
  ClockIcon,
  CpuChipIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  LightBulbIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';

export interface StoryViewProps {
  selectedDay: number;
  selectedHour: number;
  setSelectedHour: (hour: number) => void;
  currentDay: number;
  currentHour: number;
}

export function StoryView({ selectedDay, selectedHour, setSelectedHour, currentDay, currentHour }: StoryViewProps) {
  const prevHour = selectedHour - 1;

  // 判断是否在查看历史时段（结果已经发生）
  const isHistorical = selectedDay < currentDay || (selectedDay === currentDay && selectedHour < currentHour);
  // 判断是否在查看当前时段（结果正在演变）
  const isCurrent = selectedDay === currentDay && selectedHour === currentHour;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* 时间对比导航 */}
      <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <button
            onClick={() => setSelectedHour(Math.max(7, selectedHour - 1))}
            disabled={selectedHour <= 7}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-sm transition-all"
          >
            ← 上一小时
          </button>
          <div className="text-center">
            <div className="text-xs text-slate-500 mb-1">当前查看时段</div>
            <div className="text-lg font-semibold text-slate-100">
              第 {selectedDay} 天 · {selectedHour}:00-{selectedHour + 1}:00
            </div>
          </div>
          <button
            onClick={() => setSelectedHour(Math.min(22, selectedHour + 1))}
            disabled={selectedHour >= 22}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-sm transition-all"
          >
            下一小时 →
          </button>
        </div>

        {/* 时间关系说明 */}
        <div className="flex items-center justify-center gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-orange-500 rounded-full" />
            <span>{prevHour}:00 的决策</span>
          </div>
          <span>→</span>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-cyan-500 rounded-full" />
            <span>{selectedHour}:00 的结果</span>
          </div>
        </div>
      </div>

      {/* 🕐 上一时段回顾 */}
      {selectedHour > 7 && (
        <div className="bg-gradient-to-r from-orange-500/10 to-orange-500/5 rounded-lg p-6 border border-orange-500/30">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center">
              <ClockIcon className="w-6 h-6 text-orange-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-slate-100">{prevHour}:00 的关键决策</h3>
              <p className="text-sm text-slate-400">这些决策正在影响当前时段</p>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-start gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-700">
              <BoltIcon className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-medium text-orange-300 mb-1">决策：紧急补货蜜桃汁5瓶</div>
                <div className="text-sm text-slate-400 flex items-center gap-2">
                  <span>执行中</span>
                  <span className="text-slate-600">|</span>
                  <span className="text-cyan-400">预计{selectedHour + 2}:00送达</span>
                </div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-slate-900/50 rounded-lg border border-slate-700">
              <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-medium text-green-300 mb-1">决策：启动美团新客券300元</div>
                <div className="text-sm text-slate-400">
                  <span className="text-green-400">已生效</span> · 新客流入+12人
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 📍 当前环境输入 */}
      <div className="bg-gradient-to-r from-cyan-500/10 to-cyan-500/5 rounded-lg p-6 border border-cyan-500/30">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
            <CloudIcon className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{selectedHour}:00 环境输入</h3>
            <p className="text-sm text-slate-400">当前时段的外部情况</p>
          </div>
        </div>
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <CloudIcon className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-slate-300 font-medium">天气：</span>
              <span className="text-slate-400">雨天转晴，温度28°C，湿度65%</span>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <ShoppingBagIcon className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-slate-300 font-medium">竞品：</span>
              <span className="text-slate-400">茶百道（距离500米）启动&ldquo;第二杯半价&rdquo;活动</span>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <ClockIcon className="w-5 h-5 text-purple-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="text-slate-300 font-medium">时段：</span>
              <span className="text-slate-400">午高峰结束，下午茶时段开始</span>
            </div>
          </div>
        </div>
      </div>

      {/* 🧠 AI分析 */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
            <CpuChipIcon className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{selectedHour}:00 AI分析</h3>
            <p className="text-sm text-slate-400">AI是怎么想的</p>
          </div>
        </div>
        <div className="space-y-2 text-sm text-slate-300 leading-relaxed">
          <p>• 预计下午客流下降15%（雨天结束后恢复 + 竞品促销影响）</p>
          <p>• 价格敏感型客户可能分流到茶百道</p>
          <p>• 天气转晴后热饮需求可能略有上升</p>
          <p>• 蜜桃果汁库存告急(23%)，花田乌龙为主力产品，需要紧急补货</p>
        </div>
      </div>

      {/* 💡 AI决策 */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center">
            <LightBulbIcon className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{selectedHour}:00 AI决策</h3>
            <p className="text-sm text-slate-400">AI决定做什么</p>
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium text-green-400 mb-1">决策1：增加热饮推荐</div>
              <div className="text-sm text-slate-400">推荐产品：伯牙绝弦（热）、桂花乌龙（热）</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium text-green-400 mb-1">决策2：启动美团&ldquo;新客立减5元&rdquo;券</div>
              <div className="text-sm text-slate-400">预算：300元，预计覆盖60-80新客</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-slate-700/50 border border-slate-600 rounded-lg">
            <XCircleIcon className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium text-slate-300 mb-1">决策3：不跟进&ldquo;第二杯半价&rdquo;活动</div>
              <div className="text-sm text-slate-400">
                理由：利润率优先（目标10-15%），差异化竞争策略，加盟店无权自主决定大型促销
              </div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
            <BoltIcon className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-medium text-orange-400 mb-1">决策4：紧急补货蜜桃果汁</div>
              <div className="text-sm text-slate-400">下单5瓶（加急配送+20%成本），预计16:00送达</div>
            </div>
          </div>
        </div>
      </div>

      {/* 📊 执行结果 */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
            <ChartBarIcon className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{selectedHour}:00 执行结果</h3>
            <p className="text-sm text-slate-400">
              {isCurrent ? '结果正在演变中...' : '实际发生了什么'}
            </p>
          </div>
        </div>

        {isHistorical ? (
          // 历史时段：显示实际结果
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-xs text-slate-500 mb-1">客流变化</div>
              <div className="text-2xl font-bold text-slate-100">-8%</div>
              <div className="text-xs text-green-400 mt-1">好于预期-15%</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-xs text-slate-500 mb-1">营收变化</div>
              <div className="text-2xl font-bold text-slate-100">持平</div>
              <div className="text-xs text-cyan-400 mt-1">热饮均价更高</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-xs text-slate-500 mb-1">利润率</div>
              <div className="text-2xl font-bold text-slate-100">12%</div>
              <div className="text-xs text-green-400 mt-1">未打折保住利润</div>
            </div>
          </div>
        ) : (
          // 当前或未来时段：显示观察中状态
          <div className="bg-slate-900/30 rounded-lg p-8 border border-slate-700/50">
            <div className="flex flex-col items-center justify-center text-center space-y-3">
              <div className="relative">
                <div className="w-16 h-16 rounded-full bg-cyan-500/10 border-2 border-cyan-500/30 flex items-center justify-center">
                  <ClockIcon className="w-8 h-8 text-cyan-400 animate-pulse" />
                </div>
                <div className="absolute inset-0 rounded-full bg-cyan-500/20 animate-ping" />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-300 mb-1">结果观察中</p>
                <p className="text-xs text-slate-500 leading-relaxed max-w-xs">
                  决策刚刚做出，实际效果需要一段时间才能体现。请继续观察后续时段的数据变化。
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <BoltIcon className="w-4 h-4" />
                <span>预计下一时段可见初步效果</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ✨ 经验总结 */}
      <div className="bg-gradient-to-br from-cyan-500/10 to-purple-500/10 rounded-lg p-6 border border-cyan-500/30">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-cyan-500/20 flex items-center justify-center">
            <LightBulbIcon className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">经验总结</h3>
            <p className="text-sm text-slate-400">这次学到了什么</p>
          </div>
        </div>
        <div className="space-y-2 text-sm text-slate-300 leading-relaxed">
          <div className="flex items-start gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span>差异化竞争比价格战更有效（保住利润率的同时维持营收）</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span>天气变化是调整产品结构的重要信号</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span>平台券可以精准吸引流失客户，ROI高于全场打折</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
            <span>紧急补货成本+20%但避免了断货损失（约¥960），决策正确</span>
          </div>
        </div>
      </div>
    </div>
  );
}
