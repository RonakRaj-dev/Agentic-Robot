import React, { useState } from 'react';
import { Bot, HelpCircle, MessageSquare, Award, BookOpen, X } from 'lucide-react';

interface HelpCenterWidgetProps {
  onOpenExplorer: () => void;
}

export const HelpCenterWidget: React.FC<HelpCenterWidgetProps> = ({ onOpenExplorer }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="fixed right-4 bottom-6 z-40">
      {isOpen ? (
        <aside className="w-72 p-5 glass-panel rounded-[2rem] border-2 border-[#6b38d4] chunky-shadow-secondary flex flex-col space-y-4 animate-fadeIn">
          <div className="flex items-center justify-between pb-3 border-b-2 border-[#efebff]">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-2xl bg-[#8455ef] text-white flex items-center justify-center border-2 border-[#6b38d4] chunky-shadow-primary">
                <Bot className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-heading font-extrabold text-sm text-[#6b38d4]">Help Center</h4>
                <p className="text-[11px] text-[#494454] font-semibold">Professor Paws AI Mascot</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 text-[#7b7486] hover:text-[#181445] rounded-full hover:bg-[#efebff] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-2 text-xs font-bold text-[#181445]">
            <button
              onClick={onOpenExplorer}
              className="w-full bg-[#b2f746] text-[#121f00] p-3 rounded-xl border-2 border-[#446900] chunky-shadow-secondary btn-press flex items-center gap-2 text-left cursor-pointer"
            >
              <MessageSquare className="w-4 h-4 text-[#446900]" />
              <span>Ask Mascot Help</span>
            </button>

            <button
              onClick={onOpenExplorer}
              className="w-full bg-[#ffffff] hover:bg-[#efebff] text-[#181445] p-2.5 rounded-xl border border-[#cbc3d7] flex items-center gap-2 text-left transition-colors cursor-pointer"
            >
              <BookOpen className="w-4 h-4 text-[#6b38d4]" />
              <span>Learning Guide</span>
            </button>

            <button
              onClick={onOpenExplorer}
              className="w-full bg-[#ffffff] hover:bg-[#efebff] text-[#181445] p-2.5 rounded-xl border border-[#cbc3d7] flex items-center gap-2 text-left transition-colors cursor-pointer"
            >
              <Award className="w-4 h-4 text-[#fb923c]" />
              <span>My Awards & Badges</span>
            </button>
          </div>

          <button
            onClick={onOpenExplorer}
            className="w-full bg-[#6b38d4] text-white py-2.5 rounded-xl border-2 border-[#6b38d4] chunky-shadow-primary btn-press font-heading font-extrabold text-xs text-center cursor-pointer"
          >
            Chat Now 💬
          </button>
        </aside>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="px-4 py-3 bg-[#6b38d4] text-white font-heading font-extrabold text-xs rounded-full border-2 border-[#6b38d4] chunky-shadow-primary btn-press flex items-center gap-2 hover:scale-105 transition-all shadow-xl cursor-pointer"
        >
          <Bot className="w-5 h-5 text-[#b2f746]" />
          <span>Ask Professor Paws</span>
          <HelpCircle className="w-4 h-4 text-white/80" />
        </button>
      )}
    </div>
  );
};
