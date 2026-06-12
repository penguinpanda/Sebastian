interface LoadingStateProps {
  text?: string;
  className?: string;
}

export default function LoadingState({ text = '加载中...', className = '' }: LoadingStateProps) {
  return <p className={`text-gray-500 ${className}`.trim()}>{text}</p>;
}
