'use client';

import { useState } from 'react';
import * as React from 'react';
import {
  ClockIcon,
  BoltIcon,
  ExclamationTriangleIcon,
  TruckIcon,
  CurrencyDollarIcon,
  PaperAirplaneIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  ShoppingBagIcon,
  UserGroupIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline';

import { StoryView } from './components/StoryView';
import { SuggestionCard, type Suggestion, type Observer } from './components/SuggestionCard';
import { MetricCard } from './components/MetricCard';
import { EventItem } from './components/EventItem';
import { ModeToggle, type ViewMode } from './components/ModeToggle';
import { DecisionPanel, MOCK_SCENARIOS } from './components/DecisionPanel';
import { PlaybackControl } from './components/PlaybackControl';

type TimeRange = 'hour' | 'day' | 'week' | 'month' | 'all';

interface Tag {
  id: string;
  label: string;
  color: string;
  category: 'env' | 'exec' | 'decision' | 'crisis';
}

const MOCK_TAGS: Tag[] = [
  { id: 'weather-rain', label: '雨天', color: 'blue', category: 'env' },
  { id: 'holiday', label: '节假日', color: 'purple', category: 'env' },
  { id: 'competitor-promo', label: '竞品促销', color: 'red', category: 'env' },
  { id: 'group-campaign', label: '集团活动', color: 'green', category: 'exec' },
  { id: 'inventory-low', label: '库存告急', color: 'orange', category: 'exec' },
  { id: 'staff-shortage', label: '人手不足', color: 'yellow', category: 'exec' },
  { id: 'crisis', label: '危机事件', color: 'red', category: 'crisis' },
];

const MOCK_OBSERVERS: Observer[] = [
  { id: 'obs-1', name: '周俊杰', avatar: '👨‍💼', role: '运营中心·门店管理组', acceptanceRate: 78, totalSuggestions: 23 },
  { id: 'obs-2', name: '苏婉清', avatar: '👩‍🔬', role: 'AI研究院·行为分析实验室', acceptanceRate: 45, totalSuggestions: 15 },
  { id: 'obs-3', name: '方嘉诚', avatar: '👔', role: '用户增长中心·零售策略部', acceptanceRate: 62, totalSuggestions: 18 },
  { id: 'obs-4', name: '夏雨晨', avatar: '🎮', role: '产品体验团', acceptanceRate: 12, totalSuggestions: 8 },
];

const MOCK_SUGGESTIONS: Suggestion[] = [
  {
    id: 'sug-1',
    observerId: 'obs-1',
    observerName: '周俊杰',
    observerAvatar: '👨‍💼',
    content: '午高峰快结束了，建议提前备货蜜桃汁，下午茶时段花田乌龙销量会上升',
    dayNumber: 45,
    timestamp: '14:25',
    hour: 14,
    contextTags: ['库存低', '午高峰后', '下午茶时段'],
    status: 'accepted',
    acceptanceRate: 78,
    aiResponse: {
      decision: 'accept',
      reasoning: '当前蜜桃汁库存仅剩23%，低于安全线(30%)。历史数据显示下午茶时段(14:00-17:00)花田乌龙销量占比从12%提升至18%。建议采纳。',
      executionPlan: '已下单蜜桃汁5瓶(加急配送)，预计16:00送达。同步通知店员准备推荐话术。',
      executed: true,
    },
  },
  {
    id: 'sug-2',
    observerId: 'obs-4',
    observerName: '夏雨晨',
    observerAvatar: '🎮',
    content: '可以考虑推出买一送一活动吸引客流',
    dayNumber: 45,
    timestamp: '14:18',
    hour: 14,
    contextTags: ['午高峰'],
    status: 'rejected',
    acceptanceRate: 12,
    aiResponse: {
      decision: 'reject',
      reasoning: '霸王茶姬品牌定位为"高性价比原叶鲜奶茶"，门店利润率目标10-15%。买一送一活动会导致单日利润下降50%以上，不符合财务模型。此外，作为加盟店无权自主决定大型促销活动，需集团统一安排。',
    },
  },
  {
    id: 'sug-3',
    observerId: 'obs-2',
    observerName: '苏婉清',
    observerAvatar: '👩‍🔬',
    content: '观察到竞品茶百道正在促销，建议分析其对客流的影响并调整营销策略',
    dayNumber: 45,
    timestamp: '13:52',
    hour: 13,
    contextTags: ['竞品促销', '客流下降'],
    status: 'accepted',
    acceptanceRate: 45,
    aiResponse: {
      decision: 'accept',
      reasoning: '茶百道距离本店500米，其"第二杯半价"活动确实会分流部分价格敏感型顾客。建议采纳并进行对策分析。',
      executionPlan: '已启动竞品影响分析模块，预计14:30完成报告。同时在美团平台增加"新客立减5元"券投放，精准吸引价格敏感用户。',
      executed: true,
    },
  },
  {
    id: 'sug-4',
    observerId: 'obs-3',
    observerName: '方嘉诚',
    observerAvatar: '👔',
    content: '注意到今日订单等待时间略长(8分钟)，建议检查是否需要增加人手',
    dayNumber: 45,
    timestamp: '14:32',
    hour: 14,
    contextTags: ['人手不足', '午高峰'],
    status: 'pending',
    acceptanceRate: 62,
  },
];

type PlaybackState = 'not_started' | 'playing' | 'paused' | 'ended';
type PlaybackSpeed = 1 | 2 | 5 | 10;

export default function ShopkeeperDashboard() {
  const [viewMode, setViewMode] = useState<ViewMode>('observation');
  const [timeRange, setTimeRange] = useState<TimeRange>('day');

  // 故事模式：当前AI经营进度
  const [currentDay, setCurrentDay] = useState(45);
  const [currentHour, setCurrentHour] = useState(14);

  // 用户查看位置（可以回溯）
  const [selectedDay, setSelectedDay] = useState(45);
  const [selectedHour, setSelectedHour] = useState(14);

  // 播放控制
  const [playbackState, setPlaybackState] = useState<PlaybackState>('paused');
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);

  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [suggestions, setSuggestions] = useState<Suggestion[]>(MOCK_SUGGESTIONS);
  const [newSuggestion, setNewSuggestion] = useState('');
  const [currentObserver] = useState<Observer>(MOCK_OBSERVERS[0]); // 当前观测者身份
  const [currentScenario] = useState(MOCK_SCENARIOS[0]); // 当前培训场景

  // 计算实际日期：从2025-03-01开始
  const getActualDate = (dayNumber: number) => {
    const startDate = new Date('2025-03-01');
    const actualDate = new Date(startDate);
    actualDate.setDate(startDate.getDate() + dayNumber - 1);
    return actualDate.toISOString().split('T')[0];
  };

  const toggleTag = (tagId: string) => {
    setActiveTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const handleSubmitSuggestion = () => {
    if (!newSuggestion.trim()) return;

    const suggestion: Suggestion = {
      id: `sug-${Date.now()}`,
      observerId: currentObserver.id,
      observerName: currentObserver.name,
      observerAvatar: currentObserver.avatar,
      content: newSuggestion,
      dayNumber: selectedDay,
      timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      hour: selectedHour,
      contextTags: ['自定义建议'],
      status: 'pending',
      acceptanceRate: currentObserver.acceptanceRate,
    };

    setSuggestions([suggestion, ...suggestions]);
    setNewSuggestion('');

    // 模拟AI处理(3秒后)
    setTimeout(() => {
      setSuggestions((prev) =>
        prev.map((s) =>
          s.id === suggestion.id
            ? {
                ...s,
                status: Math.random() > 0.3 ? 'accepted' : 'rejected',
                aiResponse: {
                  decision: Math.random() > 0.3 ? 'accept' : 'reject',
                  reasoning: '正在分析您的建议，结合当前经营数据和历史经验进行评估...',
                  executionPlan: Math.random() > 0.3 ? '已制定执行计划，将在下一决策周期实施。' : undefined,
                },
              }
            : s
        )
      );
    }, 3000);
  };

  const handleDecision = (optionId: string) => {
    console.log('学员选择了决策:', optionId);
    // TODO: 调用后端API模拟决策结果
  };

  // 播放控制
  const togglePlayback = () => {
    if (playbackState === 'playing') {
      setPlaybackState('paused');
    } else if (playbackState === 'paused' || playbackState === 'not_started') {
      setPlaybackState('playing');
    }
  };

  const jumpToCurrent = () => {
    setSelectedDay(currentDay);
    setSelectedHour(currentHour);
  };

  const isViewingCurrent = selectedDay === currentDay && selectedHour === currentHour;

  // 自动播放逻辑
  React.useEffect(() => {
    if (playbackState !== 'playing' || viewMode !== 'observation') return;

    const interval = setInterval(() => {
      setCurrentHour((prevHour) => {
        const nextHour = prevHour + 1;
        if (nextHour >= 24) {
          setCurrentDay((prevDay) => {
            const nextDay = prevDay + 1;
            if (nextDay > 180) {
              setPlaybackState('ended');
              return 180;
            }
            return nextDay;
          });
          return 0;
        }
        return nextHour;
      });
    }, 1000 / playbackSpeed); // 根据速度调整间隔

    return () => clearInterval(interval);
  }, [playbackState, playbackSpeed, viewMode]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* 顶部：时间轴导航 + 标题 */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">
                AI店长模拟经营
              </h1>
              <p className="text-xs text-slate-400 mt-1">
                {viewMode === 'observation'
                  ? '跟随AI店长的经营故事，观察决策过程'
                  : '在模拟环境中做决策，获得实时反馈'}
              </p>
            </div>

            {/* 模式切换 - 居中 */}
            <div className="absolute left-1/2 transform -translate-x-1/2">
              <ModeToggle mode={viewMode} onModeChange={setViewMode} />
            </div>

            <div className="flex items-center gap-3 text-sm">
              {viewMode === 'observation' ? (
                <PlaybackControl
                  playbackState={playbackState}
                  playbackSpeed={playbackSpeed}
                  onTogglePlayback={togglePlayback}
                  onSpeedChange={setPlaybackSpeed}
                  currentDay={currentDay}
                  currentHour={currentHour}
                  selectedDay={selectedDay}
                  selectedHour={selectedHour}
                  onJumpToCurrent={jumpToCurrent}
                />
              ) : (
                <>
                  <div className="px-3 py-1.5 bg-slate-800/50 rounded-lg">
                    <ClockIcon className="w-4 h-4 inline mr-1.5 text-slate-400" />
                    <span className="text-slate-300">第 {selectedDay} 天</span>
                    <span className="text-slate-500 mx-2">·</span>
                    <span className="text-slate-300">{selectedHour}:00</span>
                  </div>
                  <div className="px-3 py-1.5 bg-slate-800/50 rounded-lg text-slate-400">
                    {getActualDate(selectedDay)}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* 时间轴 */}
          <div className="space-y-2">
            {viewMode === 'observation' && (
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 bg-orange-500 rounded-full" />
                    <span className="text-slate-400">
                      AI当前: 第{currentDay}天 {currentHour}:00
                    </span>
                  </div>
                  {selectedDay !== currentDay || selectedHour !== currentHour ? (
                    <div className="flex items-center gap-1.5">
                      <div className="w-2 h-2 bg-cyan-400 rounded-full" />
                      <span className="text-slate-400">
                        查看: 第{selectedDay}天 {selectedHour}:00
                      </span>
                    </div>
                  ) : null}
                </div>
                <span className="text-slate-500">
                  {getActualDate(currentDay)}
                </span>
              </div>
            )}
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 whitespace-nowrap">第1天</span>
            <div className="flex-1 h-8 bg-slate-800/50 rounded-lg relative overflow-hidden">
              {/* 180天时间轴 */}
              <div className="absolute inset-0 flex">
                {Array.from({ length: 180 }).map((_, i) => {
                  const isKeyEvent = i === 15 || i === 45 || i === 78 || i === 120;
                  const isBeforeCurrent = i < currentDay - 1;
                  const isAfterCurrent = i >= currentDay;
                  return (
                    <div
                      key={i}
                      className={`flex-1 border-r border-slate-700/50 transition-all relative ${
                        i === selectedDay - 1 ? 'bg-cyan-500/30' : ''
                      } ${isBeforeCurrent ? 'bg-slate-700/30' : ''} ${
                        isAfterCurrent ? 'cursor-not-allowed opacity-50' : 'cursor-pointer hover:bg-cyan-500/20'
                      }`}
                      onClick={() => !isAfterCurrent && setSelectedDay(i + 1)}
                    >
                      {i % 30 === 0 && <div className="absolute top-0 left-0 w-px h-full bg-slate-500" />}
                      {/* 关键事件标记 */}
                      {isKeyEvent && (
                        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                          <div className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" title="关键事件" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* 当前AI经营进度指示器（橙色） */}
              <div
                className="absolute top-0 bottom-0 w-1 bg-orange-500 shadow-lg shadow-orange-500/50 z-20 pointer-events-none"
                style={{ left: `${(currentDay / 180) * 100}%` }}
                title="当前AI经营进度"
              >
                <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-orange-500 rounded-full border-2 border-slate-900" />
              </div>

              {/* 用户查看位置指示器（青色） */}
              {!isViewingCurrent && (
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-lg shadow-cyan-400/50 z-10 pointer-events-none"
                  style={{ left: `${(selectedDay / 180) * 100}%` }}
                  title="查看位置"
                >
                  <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-cyan-400 rounded-full" />
                </div>
              )}
            </div>
            <span className="text-xs text-slate-500 whitespace-nowrap">第180天</span>
            </div>
          </div>
        </div>
      </header>

      {/* 主体布局 */}
      <div className="flex flex-1 overflow-hidden">
        {/* 左侧边栏 - 时间控制 + 标签筛选 */}
        <aside className="w-64 border-r border-slate-800 bg-slate-900/30 overflow-y-auto">
          <div className="p-4 space-y-6">
            {/* 时间范围选择 */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                时间范围
              </h3>
              <div className="space-y-2">
                {(['hour', 'day', 'week', 'month', 'all'] as TimeRange[]).map((range) => (
                  <button
                    key={range}
                    onClick={() => setTimeRange(range)}
                    className={`w-full text-left px-3 py-2 rounded-md text-sm transition-all ${
                      timeRange === range
                        ? 'bg-slate-700 text-slate-100'
                        : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                    }`}
                  >
                    {range === 'hour' && '过去1小时'}
                    {range === 'day' && '今日'}
                    {range === 'week' && '本周'}
                    {range === 'month' && '本月'}
                    {range === 'all' && '全部180天'}
                  </button>
                ))}
              </div>
            </div>

            {/* 场景筛选 - 徽章式 */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                场景筛选
              </h3>
              <p className="text-xs text-slate-500 mb-3">快速定位有教学价值的关键场景</p>
              <div className="flex flex-wrap gap-2">
                {MOCK_TAGS.map((tag) => {
                  const isActive = activeTags.includes(tag.id);
                  const colorClasses = {
                    blue: isActive ? 'bg-blue-500/30 text-blue-300 border-blue-400' : 'bg-blue-500/10 text-blue-400/60 border-blue-500/30',
                    purple: isActive ? 'bg-purple-500/30 text-purple-300 border-purple-400' : 'bg-purple-500/10 text-purple-400/60 border-purple-500/30',
                    red: isActive ? 'bg-red-500/30 text-red-300 border-red-400' : 'bg-red-500/10 text-red-400/60 border-red-500/30',
                    green: isActive ? 'bg-green-500/30 text-green-300 border-green-400' : 'bg-green-500/10 text-green-400/60 border-green-500/30',
                    orange: isActive ? 'bg-orange-500/30 text-orange-300 border-orange-400' : 'bg-orange-500/10 text-orange-400/60 border-orange-500/30',
                    yellow: isActive ? 'bg-yellow-500/30 text-yellow-300 border-yellow-400' : 'bg-yellow-500/10 text-yellow-400/60 border-yellow-500/30',
                  };
                  return (
                    <button
                      key={tag.id}
                      onClick={() => toggleTag(tag.id)}
                      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all border ${
                        colorClasses[tag.color as keyof typeof colorClasses]
                      } ${isActive ? 'shadow-sm' : 'hover:bg-opacity-20'}`}
                    >
                      {tag.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 快速跳转 */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                关键节点
              </h3>
              <div className="space-y-2 text-sm">
                <button className="w-full text-left px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200">
                  <ExclamationTriangleIcon className="w-4 h-4 inline mr-2 text-red-400" />
                  危机事件 (3)
                </button>
                <button className="w-full text-left px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200">
                  <BoltIcon className="w-4 h-4 inline mr-2 text-yellow-400" />
                  重大决策 (12)
                </button>
                <button className="w-full text-left px-3 py-2 rounded-md text-slate-400 hover:bg-slate-800 hover:text-slate-200">
                  <ChartBarIcon className="w-4 h-4 inline mr-2 text-green-400" />
                  盈利高峰 (5)
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* 中央主区域 - 完整故事展示 */}
        <main className="flex-1 overflow-y-auto">
          <div className="p-6">
            <StoryView
              selectedDay={selectedDay}
              selectedHour={selectedHour}
              setSelectedHour={setSelectedHour}
              currentDay={currentDay}
              currentHour={currentHour}
            />
          </div>
        </main>

        {/* 右侧面板 - 根据模式显示不同内容 */}
        <aside className="w-96 border-l border-slate-800 bg-slate-900/30 flex flex-col">
          {viewMode === 'observation' ? (
            <>
              {/* 故事模式：Tab切换 */}
              <div className="flex border-b border-slate-800 bg-slate-900/50">
                <button
                  onClick={() => setShowSuggestions(false)}
                  className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${
                    !showSuggestions
                      ? 'text-cyan-400 border-b-2 border-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ChartBarIcon className="w-4 h-4 inline mr-2" />
                  实时指标
                </button>
                <button
                  onClick={() => setShowSuggestions(true)}
                  className={`flex-1 px-4 py-3 text-sm font-medium transition-all ${
                    showSuggestions
                      ? 'text-cyan-400 border-b-2 border-cyan-400'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ChatBubbleLeftRightIcon className="w-4 h-4 inline mr-2" />
                  观众建议
                  <span className="ml-2 px-1.5 py-0.5 text-xs bg-orange-500/20 text-orange-400 rounded">
                    {suggestions.filter((s) => s.status === 'pending').length}
                  </span>
                </button>
              </div>

              {/* 故事模式内容区 */}
              <div className="flex-1 overflow-y-auto">
            {!showSuggestions ? (
              <div className="p-4 space-y-4">
                {/* 关键指标卡片 */}
                <MetricCard
                  icon={<CurrencyDollarIcon className="w-5 h-5" />}
                  label="今日营收"
                  value="¥9,845"
                  change="+12.3%"
                  trend="up"
                />
                <MetricCard
                  icon={<ShoppingBagIcon className="w-5 h-5" />}
                  label="订单量"
                  value="428"
                  change="+8.5%"
                  trend="up"
                />
                <MetricCard
                  icon={<UserGroupIcon className="w-5 h-5" />}
                  label="在岗人数"
                  value="3/5"
                  change="正常"
                  trend="neutral"
                />
                <MetricCard
                  icon={<TruckIcon className="w-5 h-5" />}
                  label="库存状态"
                  value="充足"
                  change="82%"
                  trend="neutral"
                />

                {/* 实时事件流 */}
                <div className="mt-6">
                  <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                    实时事件流
                  </h3>
                  <div className="space-y-2">
                    <EventItem time="14:28" type="decision" message="AI决策: 增加伯牙绝弦备货200杯" />
                    <EventItem time="14:15" type="warning" message="警告: 蜜桃果汁库存低于安全线" />
                    <EventItem time="14:00" type="info" message="午高峰结束，产能恢复正常" />
                    <EventItem time="13:45" type="success" message="完成订单峰值处理，等待时间8分钟" />
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col h-full">
                {/* 输入区域 - 移到顶部 */}
                <div className="p-4 border-b border-slate-700 bg-slate-900/50">
                  <div className="relative">
                    <textarea
                      value={newSuggestion}
                      onChange={(e) => setNewSuggestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSubmitSuggestion();
                        }
                      }}
                      placeholder="给AI店长提建议..."
                      rows={3}
                      className="w-full px-3 py-3 pr-12 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500 resize-none"
                    />
                    {newSuggestion.trim() && (
                      <button
                        onClick={handleSubmitSuggestion}
                        className="absolute right-2 bottom-2 p-2 text-cyan-400 hover:text-cyan-300 hover:bg-slate-700/50 rounded-lg transition-all"
                      >
                        <PaperAirplaneIcon className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-2">
                    <LightBulbIcon className="w-3 h-3 inline mr-1" />
                    AI店长会根据当前经营状况评估您的建议
                  </div>
                </div>

                {/* 建议列表 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {suggestions.map((suggestion) => (
                    <SuggestionCard key={suggestion.id} suggestion={suggestion} />
                  ))}
                  {suggestions.length === 0 && (
                    <div className="text-center py-12 text-slate-500">
                      <LightBulbIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>暂无建议</p>
                    </div>
                  )}
                </div>
              </div>
            )}
              </div>
            </>
          ) : (
            <>
              {/* 培训模式：决策面板 */}
              <div className="border-b border-slate-800 bg-slate-900/50 px-4 py-3">
                <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                  <LightBulbIcon className="w-4 h-4" />
                  决策训练场景
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  根据场景做出决策，系统将模拟结果
                </p>
              </div>
              <DecisionPanel scenario={currentScenario} onDecision={handleDecision} />
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

