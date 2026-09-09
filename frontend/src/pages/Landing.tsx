import React, { useState } from 'react';
import { TouchKeyboard } from '../components/common/TouchKeyboard';

interface LandingProps {
  onStartDemo: () => void;
  onAskQuestion?: (q: string) => void;
}

export const Landing: React.FC<LandingProps> = ({ onStartDemo, onAskQuestion }) => {
  const [inputText, setInputText] = useState('');
  const [showKeyboard, setShowKeyboard] = useState(false);

  const bentoQuestions = [
    {
      title: 'Why do plants need sunlight?',
      icon: 'eco',
      bg: 'bg-[#fecb00]',
      textColor: 'text-[#6e5700]',
      query: 'Why do plants need sunlight for photosynthesis?',
    },
    {
      title: 'How does photosynthesis work?',
      icon: 'water_drop',
      bg: 'bg-[#72fe88]',
      textColor: 'text-[#002107]',
      query: 'How does photosynthesis work step by step in plants?',
    },
    {
      title: 'What are the main states of matter?',
      icon: 'science',
      bg: 'bg-[#ffdad5]',
      textColor: 'text-[#930005]',
      query: 'What are solid, liquid, and gas states of matter?',
    },
    {
      title: 'Generate 3D Video Demo Prompt',
      icon: 'videocam',
      bg: 'bg-[#e2241f]',
      textColor: 'text-white',
      query: 'Generate a 3D animation script for Class 6 Science chapter concepts.',
    },
  ];

  const handleSend = () => {
    if (!inputText.trim()) return;
    if (onAskQuestion) {
      onAskQuestion(inputText);
    } else {
      onStartDemo();
    }
  };

  return (
    <div className="w-full flex-1 flex flex-col justify-between p-4 md:p-8 max-w-5xl mx-auto min-h-[calc(100vh-80px)]">
      {/* Robot Speech Bubble & Pixel Mascot Section */}
      <div className="flex flex-col md:flex-row items-center md:items-start gap-6 mb-6">
        {/* Robot Avatar Container with glowing green eyes */}
        <div className="w-24 h-24 md:w-28 md:h-28 bg-[#72fe88] pixel-border rounded-full flex-shrink-0 hard-shadow overflow-hidden relative flex items-center justify-center">
          <div className="text-5xl md:text-6xl animate-pulse">🤖</div>
        </div>

        {/* Speech Bubble with pixel tail */}
        <div className="flex-1 bg-[#ffffff] pixel-border p-6 pixel-corners hard-shadow relative">
          {/* Speech bubble tail for desktop */}
          <div className="hidden md:block absolute -left-[14px] top-6 w-0 h-0 border-t-[10px] border-t-transparent border-r-[12px] border-r-[#1c1b1b] border-b-[10px] border-b-transparent z-10" />
          <div className="hidden md:block absolute -left-[9px] top-6 w-0 h-0 border-t-[10px] border-t-transparent border-r-[12px] border-r-white border-b-[10px] border-b-transparent z-20" />
          
          <div className="flex items-center gap-2 mb-2">
            <span className="font-pixel text-xs font-bold text-[#bc000a] uppercase bg-[#ffdad5] px-2 py-0.5 border border-[#1c1b1b]">
              BUDDYBOT AI KIOSK
            </span>
            <span className="font-pixel text-[11px] text-[#5d3f3b] font-bold">
              • READY FOR STUDENT TOUCH INTERACTION
            </span>
          </div>
          <h1 className="font-headline font-bold text-2xl md:text-3xl text-[#1c1b1b] leading-tight">
            What would you like to learn today?
          </h1>
          <p className="font-body text-sm md:text-base text-[#5d3f3b] mt-1">
            Tap a quick question cartridge below or type any textbook query on the touch screen!
          </p>
        </div>
      </div>

      {/* Suggested Questions Bento Cartridge Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 flex-1">
        {bentoQuestions.map((q, idx) => (
          <button
            key={idx}
            onClick={() => {
              setInputText(q.query);
              if (onAskQuestion) onAskQuestion(q.query);
            }}
            className={`${q.bg} ${q.textColor} pixel-border p-5 pixel-corners hard-shadow hard-shadow-active text-left flex flex-col justify-between group min-h-[140px] cursor-pointer`}
          >
            <span className="material-symbols-outlined text-4xl mb-3 group-hover:scale-110 transition-transform">
              {q.icon}
            </span>
            <span className="font-headline font-bold text-lg md:text-xl leading-snug">
              {q.title}
            </span>
          </button>
        ))}
      </div>

      {/* Touch Input Bar with On-Screen Keyboard Toggle */}
      <div className="pt-4 border-t-[3px] border-[#1c1b1b]">
        <div className="flex gap-3 flex-col sm:flex-row">
          <div className="flex-1 bg-[#ffffff] pixel-border p-2 hard-shadow flex items-center relative h-16">
            <button
              onClick={() => setShowKeyboard(!showKeyboard)}
              className="p-2 bg-[#f0eded] text-[#1c1b1b] border-2 border-[#1c1b1b] font-pixel text-xs font-bold mr-2 hover:bg-[#eae7e7] cursor-pointer flex items-center gap-1"
              title="Toggle Touch Keyboard"
            >
              <span className="material-symbols-outlined text-xl">keyboard</span>
              <span className="hidden sm:inline">KEYBOARD</span>
            </button>
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type your textbook question here..."
              className="w-full h-full bg-transparent border-none focus:outline-none font-body text-base font-medium text-[#1c1b1b] placeholder-[#926f6a] px-2"
            />
            <div className="w-3 h-6 bg-[#1c1b1b] blinking-cursor pointer-events-none mr-2 hidden md:block" />
          </div>

          <button
            onClick={handleSend}
            className="bg-[#bc000a] text-white pixel-border px-8 h-16 hard-shadow hard-shadow-active font-pixel text-sm font-bold uppercase pixel-corners flex items-center justify-center gap-2 cursor-pointer shrink-0"
          >
            <span>ASK ROBOT</span>
            <span className="material-symbols-outlined">send</span>
          </button>
        </div>
      </div>

      {/* On-Screen Touch Keyboard Dropdown */}
      {showKeyboard && (
        <div className="mt-4">
          <TouchKeyboard
            onKeyPress={(char) => setInputText((prev) => prev + char)}
            onBackspace={() => setInputText((prev) => prev.slice(0, -1))}
            onSubmit={handleSend}
            onClose={() => setShowKeyboard(false)}
          />
        </div>
      )}
    </div>
  );
};
