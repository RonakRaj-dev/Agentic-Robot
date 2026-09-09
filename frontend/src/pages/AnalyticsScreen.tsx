import React, { useState, useEffect } from 'react';
import { fetchAnalytics, resetAnalytics, type AnalyticsData } from '../api/client';

interface AnalyticsScreenProps {
  selectedClass: number | null;
  selectedSubject: string | null;
  onBack: () => void;
}

export const AnalyticsScreen: React.FC<AnalyticsScreenProps> = ({
  selectedClass,
  selectedSubject,
  onBack,
}) => {
  const cls = selectedClass || 6;
  const activeSubj = selectedSubject || 'Science';

  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Admin & Reset States
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [showLogin, setShowLogin] = useState<boolean>(false);
  const [adminUser, setAdminUser] = useState<string>('');
  const [adminPass, setAdminPass] = useState<string>('');
  const [loginError, setLoginError] = useState<string>('');
  const [resetting, setResetting] = useState<boolean>(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAnalytics(cls, activeSubj, 'web_student');
      setData(result);
    } catch (err: any) {
      setError(err?.message || "Failed to load telemetry.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [cls, activeSubj]);

  const handleAdminLogin = () => {
    if (adminUser === 'admin' && adminPass === 'admin') {
      setIsAdmin(true);
      setShowLogin(false);
      setAdminUser('');
      setAdminPass('');
      setLoginError('');
    } else {
      setLoginError('Invalid admin username or password!');
    }
  };

  const handleReset = async () => {
    if (!window.confirm("Are you sure you want to reset all telemetry data to zero? This will permanently clear MongoDB mastery histories.")) {
      return;
    }
    setResetting(true);
    try {
      const res = await resetAnalytics('web_student');
      if (res.success) {
        alert("Telemetry successfully reset to zero in MongoDB!");
        await loadData();
      } else {
        alert("Reset failed: " + res.message);
      }
    } catch (err: any) {
      alert("Error: " + (err?.message || "Could not connect to backend reset service."));
    } finally {
      setResetting(false);
    }
  };

  const levelTitle = cls <= 5 ? 'PRIMARY EXPLORER' : cls <= 8 ? 'MIDDLE SCHOOL MASTER' : 'SENIOR ACADEMIC LEADER';

  return (
    <div className="flex-1 flex flex-col justify-start items-center px-6 pt-16 pb-24 w-full h-full max-w-6xl mx-auto overflow-y-auto">
      {/* Admin Login Modal Overlay */}
      {showLogin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#181445]/60 backdrop-blur-sm">
          <div className="w-full max-w-sm bg-[#ffffff] border-[4px] border-[#1c1b1b] p-6 brutal-shadow space-y-4">
            <div className="flex justify-between items-center border-b-2 border-[#1c1b1b] pb-2">
              <span className="font-headline font-black text-lg text-[#1c1b1b]">🔑 ADMIN PORTAL LOGIN</span>
              <button 
                onClick={() => { setShowLogin(false); setLoginError(''); }}
                className="text-[#bc000a] font-black hover:scale-110 transition-transform cursor-pointer"
              >
                [X]
              </button>
            </div>

            {loginError && (
              <div className="p-2 bg-[#ffdad5] border border-[#bc000a] text-[#bc000a] font-pixel text-[11px] font-bold text-center animate-shake">
                ⚠️ {loginError}
              </div>
            )}

            <div className="space-y-1">
              <label className="font-pixel text-[11px] font-bold uppercase text-[#5d3f3b] block">Username</label>
              <input
                type="text"
                value={adminUser}
                onChange={(e) => setAdminUser(e.target.value)}
                placeholder="Enter admin username"
                className="w-full p-2 bg-[#f0eded] border-2 border-[#1c1b1b] text-xs font-pixel font-bold focus:outline-none focus:border-[#bc000a]"
              />
            </div>

            <div className="space-y-1">
              <label className="font-pixel text-[11px] font-bold uppercase text-[#5d3f3b] block">Password</label>
              <input
                type="password"
                value={adminPass}
                onChange={(e) => setAdminPass(e.target.value)}
                placeholder="Enter admin password"
                className="w-full p-2 bg-[#f0eded] border-2 border-[#1c1b1b] text-xs font-pixel font-bold focus:outline-none focus:border-[#bc000a]"
              />
            </div>

            <button
              onClick={handleAdminLogin}
              className="w-full py-2.5 bg-[#fecb00] border-2 border-[#1c1b1b] font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer"
            >
              Authenticate 🔓
            </button>
          </div>
        </div>
      )}

      {/* Analytics Header */}
      <div className="w-full flex items-center justify-between pb-4 mb-6 border-b-[3px] border-[#1c1b1b]">
        <div>
          <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-3 py-1 border border-[#1c1b1b] uppercase inline-block mb-1">
            ROBO-OS TELEMETRY & LEARNING ANALYTICS • CLASS {cls}
          </span>
          <h2 className="font-headline font-black text-3xl text-[#1c1b1b] uppercase">
            Student Mastery Dashboard
          </h2>
        </div>

        <div className="flex space-x-3">
          {isAdmin ? (
            <>
              <button
                onClick={loadData}
                disabled={loading}
                className="px-4 py-2 bg-[#72fe88] border-[3px] border-[#1c1b1b] font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer disabled:opacity-55"
              >
                {loading ? 'Refreshing...' : 'Refresh Analytics ↻'}
              </button>
              <button
                onClick={handleReset}
                disabled={resetting || loading}
                className="px-4 py-2 bg-[#bc000a] text-white border-[3px] border-[#1c1b1b] font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer disabled:opacity-55"
              >
                {resetting ? 'Resetting...' : 'Reset Telemetry ∅'}
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className="px-4 py-2 bg-[#fecb00] border-[3px] border-[#1c1b1b] font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer"
            >
              🔒 Admin Access
            </button>
          )}
          <button
            onClick={onBack}
            className="px-4 py-2 bg-[#ffffff] border-[3px] border-[#1c1b1b] font-pixel text-xs font-bold uppercase brutal-shadow brutal-button-active cursor-pointer"
          >
            RETURN TO LESSON ↩
          </button>
        </div>
      </div>


      {loading && !data ? (
        <div className="flex-1 flex flex-col justify-center items-center py-20">
          <div className="animate-spin rounded-full h-12 w-12 border-[4px] border-[#1c1b1b] border-t-transparent mb-4"></div>
          <span className="font-pixel text-sm font-bold uppercase">Loading Dynamic Telemetry from DB...</span>
        </div>
      ) : error ? (
        <div className="w-full p-6 bg-[#ffdad5] text-[#930005] pixel-border brutal-shadow mb-8 text-center">
          <span className="font-pixel text-sm font-bold block mb-2">⚠️ ERROR LOAD TELEMETRY: {error}</span>
          <button onClick={loadData} className="px-3 py-1.5 bg-[#ffffff] border-2 border-[#1c1b1b] font-pixel text-xs font-bold uppercase">Retry</button>
        </div>
      ) : (
        <>
          {/* KPI Bento Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 w-full mb-8">
            <div className="bg-[#fecb00] text-[#6e5700] pixel-border p-5 brutal-shadow">
              <span className="font-pixel text-xs font-bold uppercase block opacity-80">MODULE ACCURACY</span>
              <span className="font-headline font-black text-4xl mt-1 block">{data?.accuracy_pct}%</span>
              <span className="font-pixel text-[10px] font-bold mt-2 block">↑ REAL-TIME DB METRIC</span>
            </div>

            <div className="bg-[#72fe88] text-[#002107] pixel-border p-5 brutal-shadow">
              <span className="font-pixel text-xs font-bold uppercase block opacity-80">QUIZ XP EARNED</span>
              <span className="font-headline font-black text-4xl mt-1 block">{data?.quiz_xp.toLocaleString()} XP</span>
              <span className="font-pixel text-[10px] font-bold mt-2 block">LEVEL {cls + 5} {levelTitle}</span>
            </div>

            <div className="bg-[#ffffff] text-[#1c1b1b] pixel-border p-5 brutal-shadow">
              <span className="font-pixel text-xs font-bold uppercase block opacity-80">RAG CONVERSATIONS</span>
              <span className="font-headline font-black text-4xl mt-1 block">{data?.asks_count} ASKS</span>
              <span className="font-pixel text-[10px] font-bold text-[#006b27] mt-2 block">100% FACT VERIFIED</span>
            </div>

            <div className="bg-[#ffdad5] text-[#930005] pixel-border p-5 brutal-shadow">
              <span className="font-pixel text-xs font-bold uppercase block opacity-80">ROS2 TELEMETRY</span>
              <span className="font-headline font-black text-4xl mt-1 block">{data?.ros2_topics} TOPICS</span>
              <span className="font-pixel text-[10px] font-bold mt-2 block">ACTIVE: /edubot/expression</span>
            </div>
          </div>

          {/* Domain Breakdown & Active Context */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full">
            {/* Subject Mastery Progress Bars */}
            <div className="bg-[#ffffff] pixel-border p-6 brutal-shadow space-y-4">
              <h3 className="font-headline font-bold text-xl text-[#1c1b1b] uppercase flex items-center justify-between border-b-2 border-[#1c1b1b] pb-2">
                <span>Subject Domain Progress</span>
                <span className="font-pixel text-xs text-[#bc000a]">CLASS {cls} NCERT</span>
              </h3>

              <div className="space-y-3">
                {data?.subject_progress && data.subject_progress.length > 0 ? (
                  data.subject_progress.map((sp) => {
                    const isSelected = sp.name.toLowerCase() === activeSubj.toLowerCase();
                    const barColor = isSelected ? '#72fe88' : sp.score >= 80 ? '#fecb00' : '#4ea8de';
                    return (
                      <div key={sp.name}>
                        <div className="flex justify-between font-pixel text-xs font-bold mb-1">
                          <span className={isSelected ? 'text-[#006b27] underline' : ''}>
                            {sp.name.replace(/_/g, ' ').toUpperCase()} {isSelected ? '★ (SELECTED)' : ''}
                          </span>
                          <span>{sp.score}%</span>
                        </div>
                        <div className="h-4 w-full bg-[#f0eded] border-2 border-[#1c1b1b]">
                          <div className="h-full" style={{ width: `${sp.score}%`, backgroundColor: barColor }} />
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <span className="font-pixel text-xs">No subject telemetry processed yet.</span>
                )}
              </div>
            </div>

            {/* Current Active Kiosk Session Context */}
            <div className="bg-[#ffffff] pixel-border p-6 brutal-shadow space-y-4">
              <h3 className="font-headline font-bold text-xl text-[#1c1b1b] uppercase border-b-2 border-[#1c1b1b] pb-2">
                Robot Kiosk Hardware Telemetry
              </h3>

              <div className="space-y-2.5 font-pixel text-xs">
                <div className="flex justify-between p-2 bg-[#f0eded] border border-[#1c1b1b]">
                  <span className="font-bold text-[#5d3f3b]">ACTIVE CLASS LEVEL:</span>
                  <span className="font-bold text-[#bc000a]">CLASS {cls}</span>
                </div>

                <div className="flex justify-between p-2 bg-[#f0eded] border border-[#1c1b1b]">
                  <span className="font-bold text-[#5d3f3b]">ACTIVE SUBJECT:</span>
                  <span className="font-bold text-[#006b27]">{activeSubj.replace(/_/g, ' ').toUpperCase()}</span>
                </div>

                <div className="flex justify-between p-2 bg-[#f0eded] border border-[#1c1b1b]">
                  <span className="font-bold text-[#5d3f3b]">HARDWARE ENGINE:</span>
                  <span className="font-bold text-[#006b27]">{data?.hardware_engine}</span>
                </div>

                <div className="flex justify-between p-2 bg-[#f0eded] border border-[#1c1b1b]">
                  <span className="font-bold text-[#5d3f3b]">ROS2 TOPIC BRIDGE:</span>
                  <span className="font-bold text-[#006b27]">/edubot/expression</span>
                </div>

                <div className="flex justify-between p-2 bg-[#f0eded] border border-[#1c1b1b]">
                  <span className="font-bold text-[#5d3f3b]">RAG VECTOR ENGINE:</span>
                  <span className="font-bold text-[#006b27]">QDRANT HIGH DENSITY</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
