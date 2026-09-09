import React, { useState, useEffect } from 'react';
import { fetchHealthCheck } from '../../api/client';

interface RobotKioskHeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedClass: number;
  selectedSubject: string;
  user?: { username: string; role: string; class_level: number } | null;
  onOpenLogin?: () => void;
  onLogout?: () => void;
}

export const RobotKioskHeader: React.FC<RobotKioskHeaderProps> = ({
  setActiveTab,
  selectedClass,
  selectedSubject,
  user,
  onOpenLogin,
  onLogout,
}) => {
  const [ros2Status, setRos2Status] = useState<string>('ROS2 MOCK MODE');
  const [currentExpression] = useState<string>('EXPRESSION_NOD');

  useEffect(() => {
    fetchHealthCheck().then((res: any) => {
      if (res && res.ros2_bridge) {
        setRos2Status(res.ros2_bridge.mode === 'rclpy' ? 'ROS2 ACTIVE' : 'ROS2 MOCK MODE');
      }
    }).catch(() => {
      setRos2Status('ROS2 MOCK MODE');
    });
  }, []);

  return (
    <header className="w-full bg-[#ffffff] border-b-[3px] border-[#1c1b1b] hard-shadow z-40 sticky top-0 px-4 py-2.5">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        {/* Left: Robot System Identity Badge */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => setActiveTab('standby')}>
          <div className="w-10 h-10 bg-[#bc000a] text-white flex items-center justify-center pixel-border hard-shadow text-xl font-black font-pixel">
            🤖
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-headline font-extrabold text-xl text-[#bc000a] tracking-tight uppercase">
                EDUBOT KIOSK
              </span>
              <span className="font-pixel text-[10px] font-bold px-2 py-0.5 bg-[#fecb00] text-[#6e5700] pixel-border uppercase">
                ROBO-OS v3.2
              </span>
            </div>
            <p className="font-pixel text-[11px] text-[#5d3f3b] font-semibold">
              Nvidia Jetson Orin Nano • Robot Tablet System
            </p>
          </div>
        </div>

        {/* Center: Live ROS2 Expression & Hardware Telemetry Bar */}
        <div className="hidden lg:flex items-center gap-4 px-4 py-1.5 bg-[#f0eded] pixel-border hard-shadow">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#72fe88] border border-[#1c1b1b] animate-pulse" />
            <span className="font-pixel text-xs font-bold text-[#006b27] uppercase">
              {ros2Status}
            </span>
          </div>

          <span className="text-[#926f6a] font-bold">|</span>

          <div className="flex items-center gap-2">
            <span className="font-pixel text-[11px] text-[#5d3f3b]">TOPIC:</span>
            <span className="font-pixel text-xs font-bold text-[#bc000a] bg-[#ffdad5] px-2 py-0.5 border border-[#1c1b1b]">
              /edubot/expression
            </span>
          </div>

          <span className="text-[#926f6a] font-bold">|</span>

          <div className="flex items-center gap-2">
            <span className="font-pixel text-[11px] text-[#5d3f3b]">EXPRESSION:</span>
            <span className="font-pixel text-xs font-bold text-[#1c1b1b] bg-[#fecb00] px-2 py-0.5 border border-[#1c1b1b]">
              {currentExpression}
            </span>
          </div>

          <span className="text-[#926f6a] font-bold">|</span>

          <div className="flex items-center gap-1.5">
            <span className="font-pixel text-xs font-bold text-[#1c1b1b]">⚡ 98%</span>
          </div>
        </div>

        {/* Right: Active Context & User Profile Button */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-[#72fe88] text-[#002107] pixel-border font-pixel text-xs font-bold">
            <span>CLASS {selectedClass}</span>
            <span>•</span>
            <span className="uppercase">{selectedSubject ? selectedSubject.replace(/_/g, ' ') : ''}</span>
          </div>

          {user ? (
            <div className="flex items-center gap-2">
              <div className="px-3 py-1 bg-[#fecb00] text-[#1c1b1b] font-pixel text-xs font-bold pixel-border">
                {user.username}
              </div>
              <button
                onClick={onLogout}
                className="p-1.5 bg-[#bc000a] text-white pixel-border hard-shadow hard-shadow-active font-pixel text-xs font-bold cursor-pointer"
                title="Log Out"
              >
                ✖
              </button>
            </div>
          ) : (
            <button
              onClick={onOpenLogin}
              className="px-4 py-1.5 bg-[#bc000a] text-white font-pixel text-xs font-bold uppercase pixel-border hard-shadow hard-shadow-active cursor-pointer"
            >
              LOGIN
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
