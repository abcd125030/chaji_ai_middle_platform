'use client';

import { PlayIcon, PauseIcon, ForwardIcon } from '@heroicons/react/24/solid';

type PlaybackState = 'not_started' | 'playing' | 'paused' | 'ended';
type PlaybackSpeed = 1 | 2 | 5 | 10;

interface PlaybackControlProps {
  playbackState: PlaybackState;
  playbackSpeed: PlaybackSpeed;
  onTogglePlayback: () => void;
  onSpeedChange: (speed: PlaybackSpeed) => void;
  currentDay: number;
  currentHour: number;
  selectedDay: number;
  selectedHour: number;
  onJumpToCurrent: () => void;
}

export function PlaybackControl({
  playbackState,
  playbackSpeed,
  onTogglePlayback,
  onSpeedChange,
  currentDay,
  currentHour,
  selectedDay,
  selectedHour,
  onJumpToCurrent,
}: PlaybackControlProps) {
  const isViewingCurrent = selectedDay === currentDay && selectedHour === currentHour;
  const isBehind = selectedDay < currentDay || (selectedDay === currentDay && selectedHour < currentHour);
  const isAhead = selectedDay > currentDay || (selectedDay === currentDay && selectedHour > currentHour);

  const speeds: PlaybackSpeed[] = [1, 2, 5, 10];

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-slate-800/50 rounded-lg border border-slate-700">
      {/* 播放/暂停按钮 */}
      <button
        onClick={onTogglePlayback}
        disabled={playbackState === 'ended'}
        className={`flex items-center justify-center w-8 h-8 rounded-full transition-all ${
          playbackState === 'ended'
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : playbackState === 'playing'
              ? 'bg-orange-500 text-white hover:bg-orange-600'
              : 'bg-cyan-500 text-white hover:bg-cyan-600'
        }`}
        title={playbackState === 'playing' ? '暂停' : '播放'}
      >
        {playbackState === 'playing' ? (
          <PauseIcon className="w-4 h-4" />
        ) : (
          <PlayIcon className="w-4 h-4 ml-0.5" />
        )}
      </button>

      {/* 速度控制 */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-slate-500 mr-1">速度:</span>
        {speeds.map((speed) => (
          <button
            key={speed}
            onClick={() => onSpeedChange(speed)}
            className={`px-2 py-1 text-xs rounded transition-all ${
              playbackSpeed === speed
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
            }`}
          >
            {speed}x
          </button>
        ))}
      </div>

      {/* 分隔线 */}
      <div className="h-5 w-px bg-slate-700" />

      {/* 跳转到当前进度 */}
      {isBehind && (
        <button
          onClick={onJumpToCurrent}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-orange-500/20 text-orange-300 border border-orange-500/30 rounded hover:bg-orange-500/30 transition-all"
        >
          <ForwardIcon className="w-3 h-3" />
          追上进度
        </button>
      )}

      {/* 当前状态显示 */}
      <div className="text-xs">
        {isAhead ? (
          <span className="text-red-400">⚠ 未来时刻</span>
        ) : isViewingCurrent && playbackSpeed === 1 ? (
          <span className="text-green-400">● 实时观看</span>
        ) : isViewingCurrent && playbackSpeed > 1 ? (
          <span className="text-cyan-400">● 加速观看 {playbackSpeed}x</span>
        ) : isBehind ? (
          <span className="text-orange-400">
            落后 {currentDay - selectedDay > 0 ? `${currentDay - selectedDay}天` : `${currentHour - selectedHour}小时`}
          </span>
        ) : (
          <span className="text-slate-500">回顾中</span>
        )}
      </div>
    </div>
  );
}
