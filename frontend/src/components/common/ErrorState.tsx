interface ErrorStateProps {
  message: string;
  className?: string;
}

export default function ErrorState({ message, className = '' }: ErrorStateProps) {
  return (
    <div className={`bg-red-50 text-red-700 p-3 rounded border border-red-200 ${className}`.trim()} role="alert">
      {message}
    </div>
  );
}
