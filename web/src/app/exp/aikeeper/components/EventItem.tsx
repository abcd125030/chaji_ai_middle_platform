interface EventItemProps {
  time: string;
  type: 'info' | 'warning' | 'success' | 'decision';
  message: string;
}

export function EventItem({ time, type, message }: EventItemProps) {
  const colorMap = {
    info: 'border-blue-500/50 bg-blue-500/10 text-blue-400',
    warning: 'border-yellow-500/50 bg-yellow-500/10 text-yellow-400',
    success: 'border-green-500/50 bg-green-500/10 text-green-400',
    decision: 'border-purple-500/50 bg-purple-500/10 text-purple-400',
  };
  return (
    <div className={`border-l-2 ${colorMap[type]} pl-3 py-2 text-xs`}>
      <div className="text-slate-500 mb-1">{time}</div>
      <div className="text-slate-300">{message}</div>
    </div>
  );
}
