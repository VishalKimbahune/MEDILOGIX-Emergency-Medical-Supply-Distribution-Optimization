import React from 'react';
import { CheckCircle2, Circle, Clock, XCircle, AlertTriangle } from 'lucide-react';

export default function OrderTimeline({ timeline = [] }) {
  if (!timeline || timeline.length === 0) return null;

  return (
    <div className="mt-3 overflow-x-auto pb-1">
      <div className="flex min-w-[540px] items-center justify-between gap-2">
        {timeline.map((step, idx) => {
          const isLast = idx === timeline.length - 1;
          let icon = <Circle className="h-4 w-4 text-slate-300" />;
          let badgeClass = 'text-slate-400';
          let barClass = 'bg-slate-200';

          if (step.rejected || step.cancelled) {
            icon = <XCircle className="h-4 w-4 text-red-600" />;
            badgeClass = 'text-red-700 font-semibold';
            barClass = 'bg-red-300';
          } else if (step.completed) {
            icon = <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
            badgeClass = 'text-emerald-800 font-semibold';
            barClass = 'bg-emerald-500';
          } else if (step.partial) {
            icon = <AlertTriangle className="h-4 w-4 text-amber-600" />;
            badgeClass = 'text-amber-800 font-semibold';
            barClass = 'bg-amber-400';
          } else if (step.current) {
            icon = <Clock className="h-4 w-4 text-sky-600" />;
            badgeClass = 'text-sky-800 font-semibold';
          }

          return (
            <React.Fragment key={step.stage}>
              <div className="flex flex-col items-center text-center">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white ring-1 ring-slate-200">
                  {icon}
                </div>
                <span className={`mt-1 whitespace-nowrap text-[10px] ${badgeClass}`}>
                  {step.stage}
                </span>
              </div>
              {!isLast && <div className={`h-0.5 flex-1 rounded-full ${barClass}`} />}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
