import React, { useState } from 'react';
import { Video, Copy, Check, Sparkles, Film, Camera, Clapperboard, X } from 'lucide-react';
import type { VideoPromptPayload } from '../../api/client';

interface VideoPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  classLevel: number;
  subject: string;
  chapterTitle: string;
  videoPrompt: VideoPromptPayload;
}

export const VideoPromptModal: React.FC<VideoPromptModalProps> = ({
  isOpen,
  onClose,
  classLevel,
  subject,
  chapterTitle,
  videoPrompt,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const MASTER_NEGATIVE_PROMPT = `No distorted faces, no extra fingers, no malformed hands, no duplicated characters, no inconsistent character appearance, no incorrect geometry, no mathematically incorrect diagrams, no incorrect scientific processes, no random symbols, no illegible text, no misspelled words, no warped objects, no flickering, no jitter, no unstable camera, no excessive motion blur, no abrupt camera movements, no confusing transitions, no cluttered composition, no dark or frightening atmosphere, no unnecessary visual effects, no low-resolution textures, no watermark, no logo, no random subtitles, no irrelevant objects.`;

  const generateFullCopyablePrompt = (): string => {
    const visualStyle = videoPrompt.visualStyle || (classLevel <= 5 ? '3D Pixar-inspired educational animation' : '3D photorealistic infographic animation');
    const cameraMotion = videoPrompt.cameraMotion || 'Slow cinematic dolly-in with soft volumetric studio lighting';
    const masterPromptText = videoPrompt.masterPrompt || `Cinematic 3D educational animation explaining '${chapterTitle}' for Class ${classLevel} ${subject} students. 4K UHD studio render with volumetric lighting.`;

    const scenesText = (videoPrompt.scenes || [])
      .map((sc: any, idx: number) => {
        const sceneNum = sc.scene || sc.scene_number || (idx + 1);
        const startTime = sc.timestampStart || sc.timestamp_start || `00:${idx * 15 < 10 ? '0' : ''}${idx * 15}`;
        const endTime = sc.timestampEnd || sc.timestamp_end || `00:${(idx + 1) * 15 < 10 ? '0' : ''}${(idx + 1) * 15}`;
        const duration = sc.durationSeconds || sc.duration_seconds || 15;
        const purpose = sc.scenePurpose || sc.scene_purpose || `Explain core concept for scene ${sceneNum}`;
        const shotType = sc.shotType || sc.shot_type || 'Wide establishing shot + slow dolly-in';
        const action = sc.action || sc.visual_prompt || sc.scene_explanation || `Detailed 3D visual animation depicting ${chapterTitle}`;
        const eduVis = sc.educationalVisualization || sc.educational_visualization || `3D labeled diagrams, visual analogies, and physical demonstrations of ${chapterTitle}`;
        const charAction = sc.characterAction || sc.character_action || 'Teacher guide demonstrating with natural pointing gestures; student watching enthusiastically';
        const camera = sc.camera || cameraMotion;
        const lighting = sc.lighting || 'Soft volumetric studio lighting, 4K UHD';
        const text = sc.onScreenText || sc.on_screen_text || `Class ${classLevel} ${subject}: ${chapterTitle}`;
        const script = sc.script || sc.narration || `Welcome! Today we explore ${chapterTitle} step by step!`;
        const sound = sc.soundEffects || sc.sound_effects || 'Soft educational chime sound effect';
        const transition = sc.transition || 'Smooth cinematic cross-dissolve to next scene';
        const takeaway = sc.learningTakeaway || sc.learning_takeaway || `Understanding the fundamental principles of ${chapterTitle}.`;

        return [
          `[SCENE ${sceneNum}]`,
          `TIMESTAMP:\n${startTime} – ${endTime}`,
          `DURATION:\n${duration} seconds`,
          `SCENE PURPOSE:\n${purpose}`,
          `SHOT TYPE:\n${shotType}`,
          `VISUAL ACTION PROMPT:\n${action}`,
          `EDUCATIONAL VISUALIZATION:\n${eduVis}`,
          `CHARACTER ACTION:\n${charAction}`,
          `CAMERA:\n${camera}`,
          `LIGHTING:\n${lighting}`,
          `ON-SCREEN TEXT:\n${text}`,
          `VOICEOVER:\n"${script}"`,
          `SOUND EFFECTS:\n${sound}`,
          `TRANSITION:\n${transition}`,
          `LEARNING TAKEAWAY:\n${takeaway}`
        ].join('\n');
      })
      .join('\n\n');

    return [
      `==================================================`,
      `EDUCATIONAL 3D VIDEO GENERATION PROMPT`,
      `==================================================`,
      ``,
      `TITLE:\n${chapterTitle} - 3D Educational Video Lesson`,
      `CLASS:\nClass ${classLevel}`,
      `SUBJECT:\n${subject}`,
      `CHAPTER:\n${chapterTitle}`,
      `TOPIC:\n${chapterTitle} Core Concepts`,
      `DURATION:\n${(videoPrompt.scenes || []).length * 15 || 60} seconds`,
      `LEARNING OBJECTIVES:\n1. Understand fundamental concepts of ${chapterTitle}\n2. Connect concepts to everyday real-world applications\n3. Master step-by-step problem solving and NCERT standards`,
      `VISUAL STYLE:\n${visualStyle}`,
      `CHARACTER DESIGN:\nConsistent warm teacher guide and curious student character in colorful attire`,
      `GLOBAL ENVIRONMENT:\nBright, modern, welcoming 3D interactive classroom environment`,
      ``,
      `MASTER PROMPT:\n${masterPromptText}`,
      ``,
      `==================================================`,
      `SCENE-BY-SCENE SCRIPT`,
      `==================================================`,
      ``,
      `${scenesText}`,
      ``,
      `==================================================`,
      `RECAP`,
      `==================================================`,
      `Visually summarize ${chapterTitle} using 3D icons, labeled diagrams, and key terms.`,
      ``,
      `==================================================`,
      `NEGATIVE PROMPT`,
      `==================================================`,
      `${MASTER_NEGATIVE_PROMPT}`,
      ``,
      `==================================================`,
      `FINAL GENERATION INSTRUCTION`,
      `==================================================`,
      `Generate the video as one cohesive educational experience. Maintain character, environment, lighting, color palette, mathematical/scientific accuracy and visual continuity throughout the entire video.`
    ].join('\n');
  };


  const fullPromptText = generateFullCopyablePrompt();

  const handleCopy = () => {
    navigator.clipboard.writeText(fullPromptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white w-full max-w-3xl rounded-3xl shadow-2xl overflow-hidden border border-slate-100 flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-6 bg-gradient-to-r from-purple-600 to-indigo-600 text-white flex items-start justify-between relative">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white">
              <Video className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 text-xs font-bold text-purple-200 uppercase tracking-wider">
                <span>Class {classLevel}</span> • <span>{subject}</span>
              </div>
              <h2 className="font-heading text-2xl font-bold text-white">
                Chapter Video Generation Prompt
              </h2>
              <p className="text-xs text-purple-100 mt-0.5">{chapterTitle}</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-purple-200 hover:text-white hover:bg-white/10 rounded-full transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Modal Body Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Visual Style & Target Model Info */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-purple-50 rounded-2xl border border-purple-100 flex items-center gap-3">
              <Film className="w-5 h-5 text-purple-600" />
              <div>
                <p className="text-xs font-semibold text-purple-600 uppercase">Visual Style</p>
                <p className="text-sm font-bold text-slate-800">{videoPrompt.visualStyle}</p>
              </div>
            </div>

            <div className="p-4 bg-indigo-50 rounded-2xl border border-indigo-100 flex items-center gap-3">
              <Camera className="w-5 h-5 text-indigo-600" />
              <div>
                <p className="text-xs font-semibold text-indigo-600 uppercase">Camera Motion</p>
                <p className="text-sm font-bold text-slate-800">{videoPrompt.cameraMotion}</p>
              </div>
            </div>

            <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-100 flex items-center gap-3">
              <Sparkles className="w-5 h-5 text-emerald-600" />
              <div>
                <p className="text-xs font-semibold text-emerald-600 uppercase">Target T2V Models</p>
                <p className="text-sm font-bold text-slate-800">HunyuanVideo / Sora / Gen-3</p>
              </div>
            </div>
          </div>

          {/* Master Visual Prompt Box */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                <Clapperboard className="w-4 h-4 text-purple-600" />
                Master Text-to-Video Model Prompt
              </label>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 text-xs font-bold text-purple-600 hover:text-purple-700 bg-purple-50 hover:bg-purple-100 px-3 py-1.5 rounded-xl border border-purple-200 transition-colors"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied Prompt!' : 'Copy Prompt'}</span>
              </button>
            </div>

            <div className="p-4 bg-slate-900 text-purple-200 font-mono text-xs rounded-2xl border border-slate-800 leading-relaxed shadow-inner max-h-64 overflow-y-auto whitespace-pre-wrap select-all">
              {fullPromptText}
            </div>

          </div>

          {/* Scene Breakdown */}
          <div className="space-y-3">
            <h3 className="text-sm font-heading font-bold text-slate-800 uppercase tracking-wide">
              Scene Breakdown & Cinematic Script
            </h3>
            <div className="space-y-3">
              {videoPrompt.scenes.map((sc: any, idx: number) => {
                const sceneNum = sc.scene || sc.scene_number || (idx + 1);
                const startTime = sc.timestampStart || sc.timestamp_start || `00:${idx * 15 < 10 ? '0' : ''}${idx * 15}`;
                const endTime = sc.timestampEnd || sc.timestamp_end || `00:${(idx + 1) * 15 < 10 ? '0' : ''}${(idx + 1) * 15}`;
                const shotType = sc.shotType || sc.shot_type || '3D Cinematic Close-Up';
                const action = sc.action || sc.visual_prompt || sc.scene_explanation || '3D animation visual action';
                const script = sc.script || sc.narration || `Exploring concepts for scene ${sceneNum}`;

                return (
                  <div key={sceneNum} className="p-4 bg-slate-50 rounded-2xl border border-slate-200 space-y-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 text-xs font-bold bg-purple-600 text-white rounded-lg">
                          Scene {sceneNum}
                        </span>
                        <span className="px-2.5 py-1 text-xs font-bold bg-indigo-100 text-indigo-700 rounded-lg">
                          ⏱️ {startTime} - {endTime}
                        </span>
                      </div>
                      <span className="px-2.5 py-1 text-xs font-bold bg-purple-100 text-purple-700 rounded-lg">
                        🎥 {shotType}
                      </span>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[11px] font-extrabold text-slate-500 uppercase tracking-wider">3D Visual Action Prompt</span>
                      <p className="text-sm font-semibold text-slate-800 leading-relaxed bg-white p-3 rounded-xl border border-slate-200">{action}</p>
                    </div>

                    <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-200/60 text-xs text-slate-700">
                      <span className="font-bold text-indigo-800 uppercase text-[10px] tracking-wider block mb-0.5">🎙️ Voiceover Narration:</span>
                      <p className="text-xs font-semibold text-slate-800 italic">"{script}"</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2.5 bg-purple-600 hover:bg-purple-700 text-white font-heading font-bold rounded-2xl shadow-md transition-all active:scale-95"
          >
            Close Prompt Viewer
          </button>
        </div>
      </div>
    </div>
  );
};
