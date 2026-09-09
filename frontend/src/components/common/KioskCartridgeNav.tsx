import React from 'react';

interface KioskCartridgeNavProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const KioskCartridgeNav: React.FC<KioskCartridgeNavProps> = ({ activeTab, setActiveTab }) => {
  const navItems = [
    { id: 'standby', label: 'STANDBY', icon: 'smart_toy', color: 'bg-[#bc000a] text-white' },
    { id: 'explorer', label: 'CHAPTER CHAT', icon: 'forum', color: 'bg-[#fecb00] text-[#6e5700]' },
    { id: 'select', label: 'SELECT GRADE', icon: 'grid_view', color: 'bg-[#72fe88] text-[#002107]' },
    { id: 'flashcards', label: 'FLASHCARDS', icon: 'style', color: 'bg-[#ffffff] text-[#1c1b1b]' },
    { id: 'quiz', label: 'QUIZ ARCADE', icon: 'workspace_premium', color: 'bg-[#e2241f] text-white' },
    { id: 'dashboard', label: 'ANALYTICS', icon: 'bar_chart', color: 'bg-[#ffffff] text-[#1c1b1b]' },
  ];

  return (
    <aside className="w-full md:w-64 bg-[#f0eded] border-r-[3px] border-[#1c1b1b] p-4 flex flex-col shrink-0">
      {/* Robot Mascot Kiosk Badge */}
      <div className="bg-[#ffffff] pixel-border hard-shadow p-4 mb-6 text-center">
        <div className="w-16 h-16 bg-[#72fe88] pixel-border rounded-full flex items-center justify-center mx-auto mb-2 hard-shadow overflow-hidden">
          <span className="text-3xl">🤖</span>
        </div>
        <h2 className="font-headline font-bold text-lg text-[#bc000a] uppercase tracking-tight">BUDDYBOT</h2>
        <span className="font-pixel text-[11px] text-[#5d3f3b] font-bold block">
          LEVEL 12 EXPLORER
        </span>
      </div>

      {/* Cartridge Navigation Touch List */}
      <nav className="space-y-3 flex-1">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 p-3.5 pixel-corners pixel-border hard-shadow hard-shadow-active font-pixel text-xs font-bold uppercase transition-all cursor-pointer ${
                isActive
                  ? `${item.color} ring-4 ring-[#1c1b1b] translate-x-1`
                  : 'bg-[#ffffff] text-[#1c1b1b] hover:bg-[#eae7e7]'
              }`}
            >
              <span className="material-symbols-outlined text-xl">{item.icon}</span>
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Robot Kiosk Power & Emergency Controls */}
      <div className="pt-6 border-t-[3px] border-[#1c1b1b] mt-4 space-y-2">
        <button
          onClick={() => setActiveTab('standby')}
          className="w-full py-3 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer"
        >
          RESET ROBOT VIEW
        </button>
        <p className="font-pixel text-[10px] text-center text-[#5d3f3b]">
          TOUCH-FIRST KIOSK INTERFACE
        </p>
      </div>
    </aside>
  );
};
