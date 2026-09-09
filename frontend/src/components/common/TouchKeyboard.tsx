import React, { useState } from 'react';

interface TouchKeyboardProps {
  onKeyPress: (char: string) => void;
  onBackspace: () => void;
  onSubmit: () => void;
  onClose: () => void;
}

export const TouchKeyboard: React.FC<TouchKeyboardProps> = ({
  onKeyPress,
  onBackspace,
  onSubmit,
  onClose,
}) => {
  const [isCaps, setIsCaps] = useState(false);

  const keysRow1 = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'];
  const keysRow2 = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'];
  const keysRow3 = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'];
  const keysRow4 = ['z', 'x', 'c', 'v', 'b', 'n', 'm'];

  return (
    <div className="bg-[#f0eded] border-t-[3px] border-[#1c1b1b] p-4 hard-shadow z-30 animate-fadeIn">
      <div className="max-w-4xl mx-auto space-y-2">
        {/* Keyboard Header */}
        <div className="flex items-center justify-between pb-2 mb-2 border-b-2 border-[#1c1b1b]">
          <span className="font-pixel text-xs font-bold text-[#bc000a] uppercase">
            ⌨ ON-SCREEN ROBOT TOUCH KEYBOARD
          </span>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-[#bc000a] text-white font-pixel text-xs font-bold pixel-border hard-shadow hard-shadow-active cursor-pointer"
          >
            HIDE KEYBOARD ✖
          </button>
        </div>

        {/* Row 1: Numbers */}
        <div className="flex justify-center gap-1.5">
          {keysRow1.map((k) => (
            <button
              key={k}
              onClick={() => onKeyPress(k)}
              className="w-10 h-12 bg-[#ffffff] text-[#1c1b1b] font-pixel text-base font-bold pixel-border hard-shadow hard-shadow-active active:bg-[#fecb00] cursor-pointer"
            >
              {k}
            </button>
          ))}
        </div>

        {/* Row 2 */}
        <div className="flex justify-center gap-1.5">
          {keysRow2.map((k) => {
            const char = isCaps ? k.toUpperCase() : k;
            return (
              <button
                key={k}
                onClick={() => onKeyPress(char)}
                className="w-10 h-12 bg-[#ffffff] text-[#1c1b1b] font-pixel text-base font-bold pixel-border hard-shadow hard-shadow-active active:bg-[#fecb00] cursor-pointer"
              >
                {char}
              </button>
            );
          })}
        </div>

        {/* Row 3 */}
        <div className="flex justify-center gap-1.5">
          {keysRow3.map((k) => {
            const char = isCaps ? k.toUpperCase() : k;
            return (
              <button
                key={k}
                onClick={() => onKeyPress(char)}
                className="w-10 h-12 bg-[#ffffff] text-[#1c1b1b] font-pixel text-base font-bold pixel-border hard-shadow hard-shadow-active active:bg-[#fecb00] cursor-pointer"
              >
                {char}
              </button>
            );
          })}
        </div>

        {/* Row 4 with Shift & Backspace */}
        <div className="flex justify-center gap-1.5">
          <button
            onClick={() => setIsCaps(!isCaps)}
            className={`px-3 h-12 font-pixel text-xs font-bold pixel-border hard-shadow hard-shadow-active cursor-pointer ${
              isCaps ? 'bg-[#fecb00] text-[#1c1b1b]' : 'bg-[#eae7e7] text-[#1c1b1b]'
            }`}
          >
            ⇧ SHIFT
          </button>
          {keysRow4.map((k) => {
            const char = isCaps ? k.toUpperCase() : k;
            return (
              <button
                key={k}
                onClick={() => onKeyPress(char)}
                className="w-10 h-12 bg-[#ffffff] text-[#1c1b1b] font-pixel text-base font-bold pixel-border hard-shadow hard-shadow-active active:bg-[#fecb00] cursor-pointer"
              >
                {char}
              </button>
            );
          })}
          <button
            onClick={onBackspace}
            className="px-3 h-12 bg-[#ffdad5] text-[#bc000a] font-pixel text-xs font-bold pixel-border hard-shadow hard-shadow-active cursor-pointer"
          >
            ⌫ BACK
          </button>
        </div>

        {/* Row 5: Space & Enter */}
        <div className="flex justify-center gap-2 pt-1">
          <button
            onClick={() => onKeyPress(' ')}
            className="flex-1 max-w-md h-12 bg-[#ffffff] text-[#1c1b1b] font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer"
          >
            SPACEBAR
          </button>
          <button
            onClick={onSubmit}
            className="px-6 h-12 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer flex items-center gap-2"
          >
            <span>SEND ASK</span>
            <span className="material-symbols-outlined text-sm">send</span>
          </button>
        </div>
      </div>
    </div>
  );
};
