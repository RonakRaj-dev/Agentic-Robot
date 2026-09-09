import React from 'react';

interface StandbyScreenProps {
  onStart: () => void;
}

export const StandbyScreen: React.FC<StandbyScreenProps> = ({ onStart }) => {
  return (
    <div className="flex-1 flex flex-col justify-center items-center relative z-10 px-8 pt-16 pb-20 w-full h-full my-auto">
      {/* Clean Dithering Background without floating components */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute inset-0 bg-dither opacity-[0.04]"></div>
      </div>

      <div className="flex flex-col items-center justify-center gap-10 w-full max-w-4xl mx-auto z-10 my-auto">
        {/* Avatar & Greeting Area */}
        <div className="flex flex-col items-center gap-6 animate-float">
          <div className="w-48 h-48 bg-[#fecb00] pixel-border brutal-shadow flex items-center justify-center relative overflow-hidden group">
            <span className="material-symbols-outlined text-[#6e5700]" style={{ fontSize: '120px' }}>
              smart_toy
            </span>
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/40 to-transparent h-2 w-full -translate-y-full group-hover:translate-y-[400%] transition-transform duration-1000 ease-in-out"></div>
          </div>

          <h1 className="font-headline text-4xl md:text-5xl font-black text-[#1c1b1b] uppercase tracking-tight flex items-center justify-center gap-2 text-center">
            <span>READY TO LEARN?</span>
            <span className="inline-block w-4 h-10 bg-[#bc000a] cursor-blink ml-2"></span>
          </h1>
        </div>

        {/* Start Button & Separate Tap Pill */}
        <div className="flex flex-col items-center gap-6 w-full">
          <button
            onClick={onStart}
            className="bg-[#bc000a] text-white font-headline text-3xl font-black uppercase px-14 py-7 pixel-border brutal-shadow hard-shadow-hover brutal-button-active flex items-center justify-center gap-4 group cursor-pointer"
          >
            <span className="material-symbols-outlined text-5xl group-hover:scale-110 transition-transform">
              play_arrow
            </span>
            <span>START LESSON</span>
          </button>

          {/* Transparent Tap Instruction Pill with Clear Gap */}
          <div className="bg-transparent pixel-border px-6 py-2.5 brutal-shadow flex items-center justify-center gap-3">
            <span className="material-symbols-outlined text-[#5d3f3b] animate-pulse text-xl">touch_app</span>
            <p className="font-pixel text-xs font-bold text-[#5d3f3b] uppercase tracking-wider">
              TAP SCREEN TO BEGIN LESSON MODULE
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
