import React, { useState } from 'react';
import { askAgentQuestion } from '../../api/client';
import type { AgentQueryResult } from '../../api/client';
import { VideoPromptModal } from '../video/VideoPromptModal';
import { TouchKeyboard } from '../common/TouchKeyboard';
import { FormattedMarkdown } from '../common/FormattedMarkdown';
import { cleanTextForSpeech } from '../../utils/textUtils';



interface AskTheBookPanelProps {
  classLevel: number;
  subject: string;
  chapterTitle: string;
}

export const AskTheBookPanel: React.FC<AskTheBookPanelProps> = ({
  classLevel,
  subject,
  chapterTitle,
}) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1);
  const [messages, setMessages] = useState<AgentQueryResult[]>([]);
  const [activeVideoModal, setActiveVideoModal] = useState<AgentQueryResult | null>(null);
  const [showTouchKeyboard, setShowTouchKeyboard] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);

  const handleSpeakAnswer = (text: string, index: number) => {
    if (!('speechSynthesis' in window)) {
      alert('Text-to-speech is not supported in this browser.');
      return;
    }

    if (speakingIndex === index) {
      window.speechSynthesis.cancel();
      setSpeakingIndex(null);
      return;
    }

    window.speechSynthesis.cancel();
    const spokenText = cleanTextForSpeech(text);
    const utterance = new SpeechSynthesisUtterance(spokenText);
    utterance.rate = 1.0;
    utterance.pitch = 1.1;

    utterance.onstart = () => setSpeakingIndex(index);
    utterance.onend = () => setSpeakingIndex(null);
    utterance.onerror = () => setSpeakingIndex(null);

    window.speechSynthesis.speak(utterance);
  };


  const handleAsk = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || loading) return;

    const userQ = query.trim();
    setQuery('');
    setLoading(true);
    setCurrentStepIndex(0);

    const stepInterval = setInterval(() => {
      setCurrentStepIndex((prev) => {
        if (prev < 4) return prev + 1;
        clearInterval(stepInterval);
        return prev;
      });
    }, 600);

    try {
      const result = await askAgentQuestion(userQ, classLevel, subject, chapterTitle);
      setTimeout(() => {
        setMessages((prev) => [result, ...prev]);
        setLoading(false);
        setCurrentStepIndex(-1);
      }, 3000);
    } catch {
      setLoading(false);
      setCurrentStepIndex(-1);
    }
  };

  return (
    <div className="bg-[#ffffff] pixel-border p-5 pixel-corners hard-shadow flex flex-col h-[740px] relative">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b-[3px] border-[#1c1b1b]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#bc000a] text-white flex items-center justify-center pixel-border hard-shadow font-pixel text-xl">
            🤖
          </div>
          <div>
            <h3 className="font-headline font-bold text-lg text-[#1c1b1b] leading-none">
              CHAPTER CHAT KIOSK
            </h3>
            <p className="font-pixel text-[11px] text-[#5d3f3b] font-semibold mt-1">
              Class {classLevel} {subject} • {chapterTitle}
            </p>
          </div>
        </div>

        <span className="font-pixel text-xs font-bold px-2.5 py-1 bg-[#72fe88] text-[#002107] pixel-border uppercase">
          REACT AGENT ACTIVE
        </span>
      </div>

      {/* Messages Stream Area */}
      <div className="flex-1 overflow-y-auto py-2 space-y-4 pr-1">
        {/* ReAct Tool Reasoning Progress Box */}
        {loading && (
          <div className="p-4 bg-[#f0eded] pixel-border space-y-2 animate-pulse">
            <div className="font-pixel text-xs font-bold text-[#bc000a] uppercase flex items-center gap-2">
              <span className="material-symbols-outlined text-base animate-spin">psychology</span>
              <span>ReAct Agent Reasoning in Progress...</span>
            </div>
            <div className="space-y-1.5 pt-1">
              {[
                'Searching NCERT Chapter Text...',
                'BM25 & Vector Retrieval...',
                'Synthesizing Response & Tone...',
                'Publishing ROS2 Expression...',
              ].map((stepName, idx) => (
                <div key={idx} className="flex items-center gap-2 font-pixel text-xs font-bold">
                  {currentStepIndex >= idx ? (
                    <span className="text-[#006b27]">✔</span>
                  ) : (
                    <span className="text-[#926f6a]">○</span>
                  )}
                  <span className={currentStepIndex >= idx ? 'text-[#1c1b1b]' : 'text-[#926f6a]'}>
                    {stepName}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {messages.length === 0 && !loading && (
          <div className="text-center py-10 space-y-4">
            <div className="w-16 h-16 rounded-full bg-[#fecb00] text-[#6e5700] pixel-border flex items-center justify-center mx-auto hard-shadow text-3xl">
              💡
            </div>
            <h4 className="font-headline font-bold text-xl text-[#1c1b1b]">
              Ask EduBot Anything About {chapterTitle}!
            </h4>
            <p className="font-body text-xs text-[#5d3f3b] max-w-xs mx-auto">
              EduBot will search the chapter text, generate grounded explanations, and update its facial expressions over ROS2!
            </p>

            {/* Quick Prompt Chips */}
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              <button
                onClick={() => setQuery(`What are the key concepts of ${chapterTitle}?`)}
                className="px-3 py-1.5 bg-[#f0eded] text-[#1c1b1b] pixel-border font-pixel text-xs font-bold hover:bg-[#fecb00] cursor-pointer"
              >
                "Key concepts?"
              </button>
              <button
                onClick={() => setQuery(`Explain ${chapterTitle} in simple terms for Class ${classLevel}.`)}
                className="px-3 py-1.5 bg-[#f0eded] text-[#1c1b1b] pixel-border font-pixel text-xs font-bold hover:bg-[#72fe88] cursor-pointer"
              >
                "Explain in simple terms"
              </button>
            </div>
          </div>
        )}

        {/* Message Items */}
        {messages.map((msg, index) => (
          <div key={index} className="space-y-3">
            {/* User Question */}
            <div className="flex justify-end">
              <div className="max-w-[85%] bg-[#bc000a] text-white p-3.5 pixel-corners pixel-border hard-shadow font-body font-bold text-sm">
                {msg.query}
              </div>
            </div>

            {/* EduBot Answer */}
            <div className="flex gap-3 items-start">
              <div className="w-8 h-8 rounded-full bg-[#72fe88] text-[#002107] pixel-border flex items-center justify-center font-pixel text-xs font-bold shrink-0 hard-shadow">
                🤖
              </div>
              <div className="bg-[#ffffff] p-4 pixel-corners pixel-border hard-shadow space-y-3 max-w-[90%]">
                {/* ReAct Execution Steps */}
                <div className="p-2.5 bg-[#f0eded] pixel-border space-y-1">
                  <p className="font-pixel text-[10px] font-bold text-[#bc000a] uppercase flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">search</span> ReAct Execution Steps:
                  </p>
                  {msg.reasoningSteps.map((step, idx) => (
                    <div key={idx} className="font-pixel text-[11px] text-[#1c1b1b]">
                      {step}
                    </div>
                  ))}
                </div>

                {/* Final Answer */}
                <FormattedMarkdown content={msg.answer} className="font-body text-sm text-[#1c1b1b] leading-relaxed" />


                {/* Citation & Video / Voice Action */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t-[2px] border-[#1c1b1b]">
                  <span className="font-pixel text-[11px] font-bold text-[#006b27]">
                    📖 {msg.citation}
                  </span>

                  <div className="flex gap-1.5">
                    <button
                      onClick={() => handleSpeakAnswer(msg.answer, index)}
                      className={`px-2.5 py-1 font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer flex items-center gap-1 ${
                        speakingIndex === index
                          ? 'bg-[#bc000a] text-white animate-pulse'
                          : 'bg-[#fecb00] text-[#6e5700]'
                      }`}
                      title="Listen to filtered human speech"
                    >
                      <span className="material-symbols-outlined text-sm">
                        {speakingIndex === index ? 'volume_off' : 'volume_up'}
                      </span>
                      <span>{speakingIndex === index ? 'STOP' : 'VOICE'}</span>
                    </button>

                    <button
                      onClick={() => setActiveVideoModal(msg)}
                      className="px-2.5 py-1 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer"
                    >
                      🎬 3D VIDEO
                    </button>
                  </div>
                </div>

              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input Form & Touch Keyboard Trigger */}
      <form onSubmit={handleAsk} className="pt-3 border-t-[3px] border-[#1c1b1b] flex items-center gap-2">
        <button
          type="button"
          onClick={() => setShowTouchKeyboard(!showTouchKeyboard)}
          className="p-3 bg-[#fecb00] text-[#6e5700] pixel-border hard-shadow hard-shadow-active font-pixel text-xs font-bold cursor-pointer"
          title="Toggle On-Screen Touch Keyboard"
        >
          <span className="material-symbols-outlined text-xl">keyboard</span>
        </button>

        <div className="flex-1 bg-[#ffffff] pixel-border p-2 hard-shadow flex items-center h-12">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`Ask EduBot about ${chapterTitle}...`}
            className="w-full h-full bg-transparent border-none focus:outline-none font-body text-sm font-medium text-[#1c1b1b] px-2"
          />
          <div className="w-2.5 h-5 bg-[#1c1b1b] blinking-cursor pointer-events-none mr-2 hidden md:block" />
        </div>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="px-5 h-12 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active disabled:opacity-50 cursor-pointer flex items-center gap-1 shrink-0"
        >
          <span>SEND</span>
          <span className="material-symbols-outlined text-base">send</span>
        </button>
      </form>

      {/* Touch Keyboard Overlay */}
      {showTouchKeyboard && (
        <div className="absolute left-0 right-0 bottom-16 z-50">
          <TouchKeyboard
            onKeyPress={(char) => setQuery((prev) => prev + char)}
            onBackspace={() => setQuery((prev) => prev.slice(0, -1))}
            onSubmit={() => {
              setShowTouchKeyboard(false);
              handleAsk();
            }}
            onClose={() => setShowTouchKeyboard(false)}
          />
        </div>
      )}

      {/* Video Prompt Modal */}
      {activeVideoModal && (
        <VideoPromptModal
          isOpen={!!activeVideoModal}
          onClose={() => setActiveVideoModal(null)}
          classLevel={classLevel}
          subject={subject}
          chapterTitle={chapterTitle}
          videoPrompt={activeVideoModal.videoPrompt}
        />
      )}
    </div>
  );
};
