import React, { useEffect } from 'react';
import { X, CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react';
import { Toast as ToastType, ToastType as ToastTypeEnum } from '../hooks/useToast';

interface ToastProps {
  toast: ToastType;
  onRemove: (id: string) => void;
}

const toastIcons = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const toastStyles = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
};

export function Toast({ toast, onRemove }: ToastProps) {
  const Icon = toastIcons[toast.type];

  useEffect(() => {
    if (toast.duration && toast.duration > 0) {
      const timer = setTimeout(() => {
        onRemove(toast.id);
      }, toast.duration);

      return () => clearTimeout(timer);
    }
  }, [toast.id, toast.duration, onRemove]);

  return (
    <div className={`flex items-center p-4 border rounded-lg shadow-lg transition-all duration-300 ${toastStyles[toast.type]}`}>
      <Icon size={20} className="flex-shrink-0 mr-3" />
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => onRemove(toast.id)}
        className="flex-shrink-0 ml-3 p-1 rounded-full hover:bg-black hover:bg-opacity-10 transition-colors"
      >
        <X size={16} />
      </button>
    </div>
  );
}