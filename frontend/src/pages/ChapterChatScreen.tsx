import React, { useState, useRef } from 'react';
import type { Chapter } from '../api/client';
import { askAgentQuestion } from '../api/client';
import type { AgentQueryResult } from '../api/client';
import { TouchKeyboard } from '../components/common/TouchKeyboard';
import { VideoPromptModal } from '../components/video/VideoPromptModal';
import { FormattedMarkdown } from '../components/common/FormattedMarkdown';
import { cleanTextForSpeech } from '../utils/textUtils';



interface ChapterChatScreenProps {
  chapter: Chapter;
  onGoToFlashcards: () => void;
  onGoToQuiz: () => void;
}

export const ChapterChatScreen: React.FC<ChapterChatScreenProps> = ({
  chapter,
  onGoToFlashcards,
  onGoToQuiz,
}) => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(-1);
  const [messages, setMessages] = useState<AgentQueryResult[]>([]);
  const [showKeyboard, setShowKeyboard] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const [showVideoModal, setShowVideoModal] = useState(false);
  const [activeVideoPrompt, setActiveVideoPrompt] = useState<any>(null);

  const keyboardRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Toggle keyboard & auto-scroll down to keyboard area
  const handleToggleKeyboard = () => {
    const nextState = !showKeyboard;
    setShowKeyboard(nextState);
    if (nextState) {
      setTimeout(() => {
        keyboardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }, 150);
    }
  };

  // Web Speech API Voice Dictation
  const handleVoiceDictation = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please type your query!');
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);

      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript) {
          setQuery((prev) => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.start();
    } catch {
      setIsListening(false);
    }
  };

  // Web Speech API Text-to-Speech for Robot Answer
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

  const handleOpenVideo = (videoPrompt?: any) => {
    const defaultPrompt = videoPrompt || {
      visualStyle: chapter.classLevel <= 5 ? '3D Pixar Educational Animation' : '3D Photorealistic Infographic',
      masterPrompt: `Cinematic 3D animation explaining '${chapter.title}' for Class ${chapter.classLevel} ${chapter.subject} students. 4K studio render with volumetric lighting.`,
      cameraMotion: 'Slow orbital pan with depth of field',
      scenes: [
        { scene: 1, action: `Visualizing ${chapter.title} concepts in 3D`, script: `Let's explore ${chapter.title} in real life!` },
        { scene: 2, action: `Step-by-step interactive diagram breakdown`, script: `Observe how all the components connect together!` }
      ]
    };
    setActiveVideoPrompt(defaultPrompt);
    setShowVideoModal(true);
  };

  const handleAsk = async (userQ?: string) => {
    const qText = userQ || query;
    if (!qText.trim() || loading) return;

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
      const result = await askAgentQuestion(qText, chapter.classLevel, chapter.subject, chapter.title);
      setTimeout(() => {
        setMessages((prev) => [result, ...prev]);
        setLoading(false);
        setCurrentStepIndex(-1);

        if ('speechSynthesis' in window && result.answer) {
          handleSpeakAnswer(result.answer, 0);
        }
      }, 3000);
    } catch {
      setLoading(false);
      setCurrentStepIndex(-1);
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between px-6 pt-16 pb-24 w-full h-full max-w-6xl mx-auto overflow-y-auto relative">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 mb-4 border-b-[3px] border-[#1c1b1b] gap-3">
        <div>
          <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-2.5 py-0.5 border border-[#1c1b1b] uppercase">
            CLASS {chapter.classLevel} {chapter.subject}
          </span>
          <h2 className="font-headline font-bold text-2xl text-[#1c1b1b] mt-1">
            {chapter.title}
          </h2>
        </div>

        {/* Option Bar including 3D Video Lesson Generator */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleOpenVideo()}
            className="px-4 py-2 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active flex items-center gap-1.5 cursor-pointer"
            title="Generate 3D Educational Video Lesson Output"
          >
            <span className="material-symbols-outlined text-base">videocam</span>
            <span>🎬 3D VIDEO LESSON</span>
          </button>
          <button
            onClick={onGoToFlashcards}
            className="px-4 py-2 bg-[#ffffff] text-[#1c1b1b] font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active cursor-pointer"
          >
            🎴 FLASHCARDS
          </button>
          <button
            onClick={onGoToQuiz}
            className="px-4 py-2 bg-[#fecb00] text-[#6e5700] font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active cursor-pointer"
          >
            🏆 QUIZ ARCADE
          </button>
        </div>
      </div>

      {/* Conversation Area */}
      <div className="flex-1 space-y-6">
        {/* Robot Speech Banner */}
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 bg-[#72fe88] pixel-border flex-shrink-0 flex items-center justify-center text-3xl brutal-shadow">
            🤖
          </div>
          <div className="bg-[#ffffff] pixel-border p-5 pixel-corners brutal-shadow relative flex-1">
            <div className="font-pixel text-xs font-bold text-[#bc000a] uppercase mb-1">
              BUDDYBOT CHAPTER CHAT & VOICE ASSISTANT
            </div>
            <p className="font-headline font-bold text-xl text-[#1c1b1b]">
              Ask EduBot any textbook question or click '3D Video Lesson' above to view animated visual explanations!
            </p>
          </div>
        </div>

        {/* Bento Suggested Questions */}
        {messages.length === 0 && !loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <button
              onClick={() => handleAsk(`Why do plants need sunlight for ${chapter.title}?`)}
              className="bg-[#fecb00] text-[#6e5700] pixel-border p-5 pixel-corners brutal-shadow brutal-button-active text-left cursor-pointer flex flex-col justify-between min-h-[120px]"
            >
              <span className="material-symbols-outlined text-3xl mb-2">eco</span>
              <span className="font-headline font-bold text-lg">Why do plants need sunlight?</span>
            </button>
            <button
              onClick={() => handleAsk(`How does ${chapter.title} work step by step?`)}
              className="bg-[#72fe88] text-[#002107] pixel-border p-5 pixel-corners brutal-shadow brutal-button-active text-left cursor-pointer flex flex-col justify-between min-h-[120px]"
            >
              <span className="material-symbols-outlined text-3xl mb-2">water_drop</span>
              <span className="font-headline font-bold text-lg">How does it work step by step?</span>
            </button>
          </div>
        )}

        {/* ReAct Step Narrator */}
        {loading && (
          <div className="p-4 bg-[#f0eded] pixel-border space-y-2 animate-pulse">
            <div className="font-pixel text-xs font-bold text-[#bc000a] uppercase flex items-center gap-2">
              <span className="material-symbols-outlined text-base animate-spin">psychology</span>
              <span>ReAct Agent Reasoning in Progress...</span>
            </div>
            <div className="space-y-1.5 pt-1">
              {[
                'Searching NCERT Chapter Text...',
                'BM25 Keyword Matching...',
                'Synthesizing Response & Persona...',
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

        {/* Messages Stream */}
        {messages.map((msg, index) => (
          <div key={index} className="space-y-3">
            <div className="flex justify-end">
              <div className="max-w-[85%] bg-[#bc000a] text-white p-4 pixel-border brutal-shadow font-body font-bold text-sm">
                {msg.query}
              </div>
            </div>

            <div className="flex gap-3 items-start">
              <div className="w-10 h-10 bg-[#72fe88] text-[#002107] pixel-border flex items-center justify-center font-pixel text-xs font-bold shrink-0 brutal-shadow">
                🤖
              </div>
              <div className="bg-[#ffffff] p-5 pixel-border brutal-shadow space-y-3 max-w-[90%] flex-1">
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

                {/* Highly Recognizable Answer Typography */}
                <FormattedMarkdown content={msg.answer} className="font-body text-base text-[#1c1b1b] leading-relaxed" />


                <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t-[2px] border-[#1c1b1b]">
                  <span className="font-pixel text-xs font-bold text-[#006b27]">
                    📖 Citation: {msg.citation}
                  </span>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleOpenVideo(msg.videoPrompt)}
                      className="px-3 py-1.5 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active flex items-center gap-1 cursor-pointer"
                    >
                      <span className="material-symbols-outlined text-base">videocam</span>
                      <span>3D VIDEO</span>
                    </button>

                    <button
                      onClick={() => handleSpeakAnswer(msg.answer, index)}
                      className={`px-3 py-1.5 font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active flex items-center gap-1 cursor-pointer ${
                        speakingIndex === index
                          ? 'bg-[#bc000a] text-white animate-pulse'
                          : 'bg-[#fecb00] text-[#6e5700]'
                      }`}
                    >
                      <span className="material-symbols-outlined text-base">
                        {speakingIndex === index ? 'volume_off' : 'volume_up'}
                      </span>
                      <span>{speakingIndex === index ? 'STOP' : 'HEAR VOICE'}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Input Bar */}
      <div className="pt-4 border-t-[3px] border-[#1c1b1b] mt-4">
        <div className="flex gap-3">
          <button
            onClick={handleToggleKeyboard}
            className="p-3 bg-[#fecb00] text-[#6e5700] pixel-border brutal-shadow brutal-button-active font-pixel text-xs font-bold cursor-pointer"
            title="Toggle Touch Keyboard"
          >
            <span className="material-symbols-outlined text-2xl">keyboard</span>
          </button>

          <button
            onClick={handleVoiceDictation}
            className={`p-3 pixel-border brutal-shadow brutal-button-active font-pixel text-xs font-bold cursor-pointer transition-colors ${
              isListening
                ? 'bg-[#bc000a] text-white animate-pulse'
                : 'bg-[#72fe88] text-[#002107]'
            }`}
            title="Voice Dictation"
          >
            <span className="material-symbols-outlined text-2xl">
              {isListening ? 'mic' : 'mic_none'}
            </span>
          </button>

          <div className="flex-1 bg-[#ffffff] pixel-border p-2 brutal-shadow flex items-center h-14">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
              placeholder={isListening ? 'Listening to your voice...' : 'Type or dictate your question here...'}
              className="w-full h-full bg-transparent border-none focus:outline-none font-body text-base font-medium text-[#1c1b1b] px-2"
            />
            <div className="w-3 h-6 bg-[#1c1b1b] cursor-blink mr-2 hidden md:block" />
          </div>

          <button
            onClick={() => handleAsk()}
            className="px-8 h-14 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border brutal-shadow brutal-button-active flex items-center gap-2 cursor-pointer shrink-0"
          >
            <span>ASK</span>
            <span className="material-symbols-outlined">send</span>
          </button>
        </div>
      </div>

      {/* Touch Keyboard Overlay */}
      {showKeyboard && (
        <div ref={keyboardRef} className="mt-4 pt-2">
          <TouchKeyboard
            onKeyPress={(char) => setQuery((prev) => prev + char)}
            onBackspace={() => setQuery((prev) => prev.slice(0, -1))}
            onSubmit={() => {
              setShowKeyboard(false);
              handleAsk();
            }}
            onClose={() => setShowKeyboard(false)}
          />
        </div>
      )}

      {/* 3D Video Lesson Output Modal */}
      {showVideoModal && (
        <VideoPromptModal
          isOpen={showVideoModal}
          onClose={() => setShowVideoModal(false)}
          classLevel={chapter.classLevel}
          subject={chapter.subject}
          chapterTitle={chapter.title}
          videoPrompt={activeVideoPrompt}
        />
      )}
    </div>
  );
};
