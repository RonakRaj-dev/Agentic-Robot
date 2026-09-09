import React from 'react';

export const BubbleBackground: React.FC = () => {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
      {/* Stitch Ambient Liquid Blobs */}
      <div 
        className="blob-bg w-[500px] h-[500px] bg-[#ffdcc5] rounded-full -top-[100px] -left-[100px] animate-float-slow"
      />
      <div 
        className="blob-bg w-[600px] h-[600px] bg-[#e3dfff] rounded-full top-[30%] -right-[200px] animate-float-reverse"
      />
      <div 
        className="blob-bg w-[450px] h-[450px] bg-[#b2f746]/40 rounded-full -bottom-[100px] left-[20%] animate-pulse-glow"
      />
      <div 
        className="blob-bg w-[400px] h-[400px] bg-[#8455ef]/20 rounded-full top-[10%] right-[25%] animate-float-slow"
      />

      {/* Floating Playful Icon Particles */}
      <svg className="absolute inset-0 w-full h-full opacity-30">
        <circle cx="10%" cy="20%" r="14" fill="#6b38d4" className="animate-float-slow" />
        <circle cx="85%" cy="15%" r="22" fill="#fb923c" className="animate-float-reverse" />
        <circle cx="75%" cy="70%" r="18" fill="#a3e635" className="animate-float-slow" />
        <circle cx="20%" cy="80%" r="12" fill="#22d3ee" className="animate-float-reverse" />
      </svg>
    </div>
  );
};

