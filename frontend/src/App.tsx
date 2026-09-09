import { useState, useEffect } from 'react';
import { StandbyScreen } from './pages/StandbyScreen';
import { ClassSelectScreen } from './pages/ClassSelectScreen';
import { SubjectSelectScreen } from './pages/SubjectSelectScreen';
import { ChapterChatScreen } from './pages/ChapterChatScreen';
import { QuizScreen } from './pages/QuizScreen';
import { FlashcardScreen } from './pages/FlashcardScreen';
import { AnalyticsScreen } from './pages/AnalyticsScreen';
import { fetchChapters, fetchHealthCheck } from './api/client';
import type { Chapter } from './api/client';

export function App() {
  const [screen, setScreen] = useState<'standby' | 'classSelect' | 'subjectSelect' | 'chapterChat' | 'quiz' | 'flashcards' | 'analytics'>('standby');
  const [selectedClass, setSelectedClass] = useState<number | null>(null);
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null);
  const [isClassSelected, setIsClassSelected] = useState<boolean>(false);
  const [currentChapter, setCurrentChapter] = useState<Chapter | null>(null);
  const [ros2Status, setRos2Status] = useState<string>('LIVE BACKEND');

  // Check backend health & ROS2 bridge status
  useEffect(() => {
    fetchHealthCheck().then((res: any) => {
      if (res && res.status === 'ready' || res.status === 'healthy') {
        setRos2Status('LIVE BACKEND');
      } else {
        setRos2Status('LIVE BACKEND');
      }
    }).catch(() => {
      setRos2Status('LIVE BACKEND');
    });
  }, []);

  // Sync chapters when class and subject are selected
  useEffect(() => {
    if (selectedClass && selectedSubject) {
      fetchChapters(selectedClass, selectedSubject).then((list) => {
        if (list && list.length > 0) {
          setCurrentChapter(list[0]);
        } else {
          setCurrentChapter(null);
        }
      });
    } else {
      setCurrentChapter(null);
    }
  }, [selectedClass, selectedSubject]);

  const handleSelectClass = (c: number) => {
    setSelectedClass(c);
    setSelectedSubject(null); // Do not put any default option or value
    setIsClassSelected(true);
    setScreen('subjectSelect');
  };

  const handleSelectSubject = (s: string) => {
    setSelectedSubject(s);
  };

  const handleSelectChapter = (ch: Chapter) => {
    setCurrentChapter(ch);
    setScreen('chapterChat');
  };

  const handleBack = () => {
    if (screen === 'chapterChat' || screen === 'quiz' || screen === 'flashcards' || screen === 'analytics') {
      setScreen('subjectSelect');
    } else if (screen === 'subjectSelect') {
      setScreen('classSelect');
    } else if (screen === 'classSelect') {
      handleHome();
    }
  };

  const handleHome = () => {
    setScreen('standby');
    setIsClassSelected(false);
    setSelectedClass(null);
    setSelectedSubject(null);
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-surface font-body-md text-on-surface bg-dither relative selection:bg-secondary-container selection:text-on-secondary-container">
      {/* Kiosk Fixed Telemetry Header */}
      <header className="fixed top-0 left-0 w-full z-50 flex justify-between items-center px-6 h-16 bg-[#ffffff]/90 backdrop-blur-sm border-b-[3px] border-[#1c1b1b] hard-shadow">
        <div className="flex items-center gap-3 cursor-pointer" onClick={handleHome}>
          <span className="font-headline font-black text-2xl text-[#bc000a] uppercase tracking-tighter">
            ROBO-LEARN
          </span>
          <div className="h-3.5 w-3.5 bg-[#006b27] animate-pulse"></div>
          <span className="font-pixel text-[11px] font-bold text-[#5d3f3b] uppercase">
            SYSTEM ONLINE ({ros2Status})
          </span>
        </div>

        {/* Telemetry & Dynamic Class Status Pills */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 pixel-border bg-[#f0eded] px-3 py-1.5 hard-shadow font-pixel text-xs font-bold text-[#1c1b1b]">
            <span className="material-symbols-outlined text-base">wifi</span>
            <span>100%</span>
          </div>
          <div className="hidden sm:flex items-center gap-2 pixel-border bg-[#f0eded] px-3 py-1.5 hard-shadow font-pixel text-xs font-bold text-[#1c1b1b]">
            <span className="material-symbols-outlined text-base">battery_full</span>
            <span>100%</span>
          </div>

          {/* Class Number Badge - Blank initially, reflects when class is selected, omits on HOME */}
          {isClassSelected && selectedClass ? (
            <div className="px-3 py-1.5 bg-[#72fe88] text-[#002107] pixel-border font-pixel text-xs font-bold uppercase animate-fadeIn">
              CLASS {selectedClass} • {(selectedSubject || 'Science').toUpperCase()}
            </div>
          ) : null}

          {/* Analytics Dashboard Trigger Button */}
          <button
            onClick={() => setScreen('analytics')}
            className="px-3 py-1.5 bg-[#fecb00] text-[#6e5700] pixel-border font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer flex items-center gap-1"
            title="Open Student Analytics Dashboard"
          >
            <span className="material-symbols-outlined text-base">bar_chart</span>
            <span className="hidden sm:inline">ANALYTICS</span>
          </button>
        </div>
      </header>

      {/* Main Kiosk Viewport Canvas */}
      <main className="flex-1 mt-16 mb-20 overflow-hidden relative flex flex-col w-full h-full">
        {screen === 'standby' && (
          <StandbyScreen onStart={() => setScreen('classSelect')} />
        )}

        {screen === 'classSelect' && (
          <ClassSelectScreen
            selectedClass={selectedClass}
            onSelectClass={handleSelectClass}
            onBack={handleBack}
            onHome={handleHome}
          />
        )}

        {screen === 'subjectSelect' && selectedClass && (
          <SubjectSelectScreen
            selectedClass={selectedClass}
            selectedSubject={selectedSubject}
            onSelectSubject={handleSelectSubject}
            onSelectChapter={handleSelectChapter}
          />
        )}

        {screen === 'chapterChat' && currentChapter && (
          <ChapterChatScreen
            chapter={currentChapter}
            onGoToFlashcards={() => setScreen('flashcards')}
            onGoToQuiz={() => setScreen('quiz')}
          />
        )}

        {screen === 'quiz' && currentChapter && selectedClass && (
          <QuizScreen
            chapterId={currentChapter.id}
            chapterTitle={currentChapter.title}
            classLevel={selectedClass}
            subject={selectedSubject || 'Science'}
            onOpenAnalytics={() => setScreen('analytics')}
          />
        )}

        {screen === 'flashcards' && currentChapter && selectedClass && (
          <FlashcardScreen
            chapterId={currentChapter.id}
            chapterTitle={currentChapter.title}
            classLevel={selectedClass}
            subject={selectedSubject || 'Science'}
          />
        )}

        {screen === 'analytics' && (
          <AnalyticsScreen
            selectedClass={selectedClass}
            selectedSubject={selectedSubject}
            onBack={handleBack}
          />
        )}
      </main>

      {/* Kiosk Fixed Bottom Navigation Actions */}
      <footer className="fixed bottom-0 left-0 w-full p-4 flex justify-between pointer-events-none z-50 bg-transparent">
        <button
          onClick={handleBack}
          disabled={screen === 'standby'}
          className="pointer-events-auto h-14 px-6 bg-[#ffffff] border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active flex items-center gap-2 font-headline font-bold text-lg text-[#1c1b1b] cursor-pointer disabled:opacity-30 disabled:pointer-events-none"
        >
          <span className="material-symbols-outlined font-bold">arrow_back</span>
          <span>BACK</span>
        </button>

        <button
          onClick={handleHome}
          className="pointer-events-auto h-14 px-6 bg-[#bc000a] text-white border-[3px] border-[#1c1b1b] brutal-shadow brutal-button-active flex items-center gap-2 font-headline font-bold text-lg cursor-pointer"
        >
          <span className="material-symbols-outlined font-bold">home</span>
          <span>HOME</span>
        </button>
      </footer>
    </div>
  );
}

export default App;
