import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { backend } from './api';

export default function Dashboard({ onLogout, initialProfile }) {
  const [profile, setProfile] = useState(initialProfile || null);
  const [activeTab, setActiveTab] = useState("command"); 
  const [routineData, setRoutineData] = useState(null);

  const [messages, setMessages] = useState([{ sender: 'ai', text: 'Systems initialized. Upload log files or type a command below.' }]);
  const [inputStr, setInputStr] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  // THE FITNESS EMOJI CYCLE
  const [fitnessEmoji, setFitnessEmoji] = useState('🏋️‍♂️');

  // THE NEW EDIT STATE
  const [showEditModal, setShowEditModal] = useState(false);
  const [editForm, setEditForm] = useState({ name: '', style: '', customStyle: '', experience: '', avatar: '' });
  const editFileRef = useRef(null);

  const handleOpenEdit = () => {
    const presets = ["Bodybuilding", "Powerlifting", "Calisthenics", "Yoga", "Athletic", "General"];
    const currentStyle = profile?.athlete_type || 'General';
    const isCustom = !presets.includes(currentStyle);

    setEditForm({
      name: profile?.name || '',
      style: isCustom ? 'Custom' : currentStyle,
      customStyle: isCustom ? currentStyle : '',
      experience: profile?.estimated_experience_level || 'Intermediate',
      avatar: profile?.avatar_color || '#FF3278'
    });
    setShowEditModal(true);
  };

  const handleEditImageConversion = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setEditForm({ ...editForm, avatar: reader.result });
    };
    reader.readAsDataURL(file);
  };

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    const finalStyle = editForm.style === 'Custom' ? editForm.customStyle : editForm.style;
    try {
      await backend.edit_active_profile(editForm.name, finalStyle, editForm.experience, editForm.avatar);
      setProfile(prev => ({ 
        ...prev, 
        name: editForm.name, 
        athlete_type: finalStyle, 
        estimated_experience_level: editForm.experience,
        avatar_color: editForm.avatar
      }));
      setShowEditModal(false);
    } catch (err) {
      console.error("Failed to save profile:", err);
    }
  };

  useEffect(() => {
    if (isThinking) {
      const emojis = ['🏋️‍♂️', '🏃‍♂️', '🧘‍♂️', '🧗‍♂️', '🤸‍♂️', '🤺'];
      let i = 0;
      const interval = setInterval(() => {
        i = (i + 1) % emojis.length;
        setFitnessEmoji(emojis[i]);
      }, 400); // Changes emoji every 400ms
      return () => clearInterval(interval);
    }
  }, [isThinking]);

  useEffect(() => {
    backend.load_active_routine().then(data => setRoutineData(data));
  }, [activeTab]); 

  useEffect(() => {
    backend.fetch_current_profile().then(data => {
      setProfile(prev => ({ ...prev, ...data }));
    });
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  // Extracted sending logic so buttons can use it!
  const sendMessageToAI = async (text) => {
    setMessages(prev => [...prev, { sender: 'user', text: text }]);
    setIsThinking(true);
    abortControllerRef.current = new AbortController();

    try {
      const result = await backend.process_query(text, abortControllerRef.current.signal);
      
      setMessages(prev => [...prev, { 
        sender: 'ai', 
        text: result.response, 
        time_taken: result.time_taken,
        require_approval: result.require_approval // Catch the approval flag
      }]);
      
      if (result.refresh_dashboard || result.route_decision === 'local') {
        backend.fetch_current_profile().then(data => setProfile(prev => ({ ...prev, ...data })));
      }

      // If we just approved a routine, instantly fetch it for the Builder tab
      if (text.toLowerCase() === 'approve' || text.toLowerCase() === 'yes') {
        backend.load_active_routine().then(data => setRoutineData(data));
      }

    } catch (err) {
      if (err.name === 'AbortError') {
        console.log("Process killed by user.");
      } else {
        setMessages(prev => [...prev, { sender: 'ai', text: '⚠️ Neural Link Disconnected. Please check server.' }]);
      }
    } finally {
      setIsThinking(false);
    }
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputStr.trim()) return;
    const text = inputStr;
    setInputStr('');
    sendMessageToAI(text);
  };

  const handleStopProcess = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort(); 
      setMessages(prev => [...prev, { sender: 'ai', text: '⚠️ Process aborted by user.' }]);
      setIsThinking(false);
    }
  };

  const handleWipeRoutine = async () => {
    if (!confirm("⚠️ Are you sure you want to completely wipe your active neural protocol? This cannot be undone.")) return;
    try {
      await backend.wipe_active_routine();
      setRoutineData(null); 
      setMessages(prev => [...prev, { sender: 'ai', text: '🗑️ Active protocol wiped from memory. Ready to architect a new baseline.' }]);
      setActiveTab("command"); 
    } catch (err) {
      console.error("Failed to wipe routine:", err);
    }
  };

  // Routine Editor State & Handlers
  const [isEditingRoutine, setIsEditingRoutine] = useState(false);

  const handleExerciseChange = (dayIdx, exIdx, field, value) => {
    const newData = [...routineData];
    newData[dayIdx].exercises[exIdx][field] = value;
    setRoutineData(newData);
  };

  const handleSaveEditedRoutine = async () => {
    try {
      await backend.commit_routine(JSON.stringify(routineData));
      setIsEditingRoutine(false);
      setMessages(prev => [...prev, { sender: 'ai', text: '✅ Neural protocol manually calibrated and saved.' }]);
    } catch (err) {
      console.error("Failed to save edited routine:", err);
    }
  };

  // Add and Delete Exercise Logic
  const handleAddExercise = (dayIdx) => {
    const newData = [...routineData];
    if (!newData[dayIdx].exercises) newData[dayIdx].exercises = [];
    newData[dayIdx].exercises.push({ name: 'New Exercise', sets: '3', reps: '8-12', explanation: 'Form notes here.' });
    setRoutineData(newData);
  };

  const handleDeleteExercise = (dayIdx, exIdx) => {
    const newData = [...routineData];
    newData[dayIdx].exercises.splice(exIdx, 1);
    setRoutineData(newData);
  };

  const handleDownloadPDF = () => {
    window.print(); // Triggers the native CSS-styled PDF export
  };

  const hasActiveRoutine = Array.isArray(routineData) && routineData.some(day => day.exercises && day.exercises.length > 0);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setMessages(prev => [...prev, { sender: 'user', text: `📎 Uploaded log: ${file.name}` }]);
    setIsThinking(true);

    try {
      const updatedProfile = await backend.upload_workout_log(file);
      if (updatedProfile.error) {
        setMessages(prev => [...prev, { sender: 'ai', text: `⚠️ Data ingestion failed: ${updatedProfile.error}` }]);
      } else {
        setProfile(prev => ({ ...prev, ...updatedProfile }));
        setMessages(prev => [...prev, { sender: 'ai', text: `✅ Data ingested successfully. Your neural weights and physical profile have been updated.` }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'ai', text: '⚠️ File transfer failed.' }]);
    } finally {
      setIsThinking(false);
      e.target.value = ''; 
    }
  };

  const getGuardrailsText = () => {
    if (!profile?.injury_or_fatigue_flags) return "None";
    if (Array.isArray(profile.injury_or_fatigue_flags)) {
      return profile.injury_or_fatigue_flags.join(", ") || "None";
    }
    try {
      const parsed = JSON.parse(profile.injury_or_fatigue_flags);
      if (Array.isArray(parsed)) return parsed.join(", ") || "None";
      return String(parsed);
    } catch (e) {
      return String(profile.injury_or_fatigue_flags);
    }
  };

  const pageVariants = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { duration: 0.5, ease: "easeOut", staggerChildren: 0.08 } } };
  const slideUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { type: "spring", damping: 22, stiffness: 110 } } };
  const tabContentVariants = {
    initial: { opacity: 0, x: 15 },
    animate: { opacity: 1, x: 0, transition: { duration: 0.4, ease: "easeOut" } },
    exit: { opacity: 0, x: -15, transition: { duration: 0.3 } }
  };

  const isImage = profile?.avatar_color && profile.avatar_color.startsWith('data:image');

  const staggerContainer = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.1 } }
  };
  const cardVariant = {
    hidden: { opacity: 0, y: 50 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 100, damping: 15 } }
  };

  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className="h-[100dvh] w-screen flex bg-surface text-white overflow-hidden font-sans relative">
      
      {/* DASHBOARD CINEMATIC AMBIENT CORE BACKGROUND */}
      <div className="absolute inset-0 w-full h-full z-0 overflow-hidden pointer-events-none">
        <video autoPlay loop muted playsInline className="absolute top-0 left-0 w-full h-full object-cover opacity-60">
          <source src={`${import.meta.env.BASE_URL}dash-bg.mp4`} type="video/mp4" />
        </video>
        <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]"></div>
      </div>

      <div className="absolute top-0 right-0 w-[800px] h-[800px] bg-cult/5 blur-[200px] rounded-full pointer-events-none"></div>

      {/* SIDEBAR */}

      <motion.nav variants={slideUp} className="w-72 bg-surfaceElevated border-r border-white/5 flex flex-col p-6 z-10 relative shadow-2xl">
        <div className="flex items-center gap-3 mb-12 mt-4">
          <div className="w-3 h-3 bg-cult rounded-full shadow-[0_0_15px_rgba(255,50,120,0.6)]"></div>
          <h2 className="text-xl font-black tracking-widest uppercase">FlexRoute</h2>
        </div>
        
        <ul className="flex flex-col gap-2 flex-1">
          <li onClick={() => setActiveTab("command")} className={`flex items-center gap-3 px-5 py-4 rounded-2xl font-bold cursor-pointer transition-all ${activeTab === 'command' ? 'bg-white/5 text-white border border-white/10 shadow-lg' : 'text-white/40 hover:bg-white/5 hover:text-white'}`}>
            <span className={activeTab === 'command' ? 'text-cult' : 'opacity-0'}>▰</span> Command Center
          </li>
          <li onClick={() => setActiveTab("routine")} className={`flex items-center gap-3 px-5 py-4 rounded-2xl font-bold cursor-pointer transition-all ${activeTab === 'routine' ? 'bg-white/5 text-white border border-white/10 shadow-lg' : 'text-white/40 hover:bg-white/5 hover:text-white'}`}>
            <span className={activeTab === 'routine' ? 'text-cult' : 'opacity-0'}>▰</span> Routine Builder
          </li>
        </ul>

        {/* User Plaque Info */}
        <div className="pt-6 mt-auto border-t border-white/5 flex items-center justify-between group">
          <div onClick={onLogout} className="cursor-pointer flex items-center gap-4 flex-1 hover:opacity-80 transition-opacity">
            <div className="w-12 h-12 rounded-full flex items-center justify-center overflow-hidden border-2 border-white/10 group-hover:border-cult/50 transition-colors flex-shrink-0">
              {isImage ? (
                <img src={profile.avatar_color} alt="Profile" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center font-black text-white" style={{ backgroundColor: profile?.avatar_color || '#FF3278' }}>
                  {profile?.name ? profile.name.charAt(0).toUpperCase() : "U"}
                </div>
              )}
            </div>
            <div className="overflow-hidden">
              <div className="font-black text-sm uppercase tracking-wider truncate w-28">{profile?.name || "Loading..."}</div>
              <div className="text-[10px] text-white/40 font-bold uppercase tracking-widest mt-1 group-hover:text-cult transition-colors">Switch Account ⎋</div>
            </div>
          </div>
          
          {/* THE NEW EDIT GEAR ICON */}
          <button onClick={handleOpenEdit} className="p-2 text-white/30 hover:text-cult hover:bg-white/5 rounded-lg transition-all" title="Edit Profile">
            ⚙️
          </button>
        </div>
      </motion.nav>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto relative z-10 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
        
        {/* Header Banner */}
        <motion.div variants={slideUp} className="h-64 flex-shrink-0 relative flex items-end p-12 border-b border-white/10 bg-gradient-to-b from-black/80 to-transparent">
          <div className="relative z-10">
            <p className="text-cult font-black text-xs tracking-[0.3em] mb-3 uppercase flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-cult rounded-full animate-pulse"></span> Active Neural Protocol
            </p>
            <h1 className="text-5xl font-black uppercase tracking-tighter drop-shadow-2xl">
              {activeTab === 'command' ? "Crush Next Session" : "Routine Architect"}
            </h1>
          </div>
        </motion.div>

        {/* Tab content area */}
        <div className="p-12 max-w-7xl w-full mx-auto flex-1 flex flex-col">
          <AnimatePresence mode="wait">
            {activeTab === 'command' ? (
              <motion.div key="command" variants={tabContentVariants} initial="initial" animate="animate" exit="exit" className="w-full flex-1 flex flex-col space-y-10">
                {/* Health Hub Widgets */}
                <div>
                  <h2 className="text-sm font-black uppercase tracking-widest mb-6 text-white/50">Health & Readiness Hub</h2>
                  <div className="grid grid-cols-3 gap-6">
                    <div className="bg-gradient-to-br from-white/5 to-transparent border border-white/5 p-8 rounded-3xl backdrop-blur-sm">
                      <h4 className="text-[10px] text-white/40 font-bold tracking-[0.2em] uppercase mb-2">Training Style</h4>
                      <p className="text-2xl font-black text-white">{profile?.athlete_type || "Unset"}</p>
                    </div>
                    <div className="bg-gradient-to-br from-white/5 to-transparent border border-white/5 p-8 rounded-3xl backdrop-blur-sm">
                      <h4 className="text-[10px] text-white/40 font-bold tracking-[0.2em] uppercase mb-2">Experience Level</h4>
                      <p className="text-2xl font-black text-white">{profile?.estimated_experience_level || "Intermediate"}</p>
                    </div>
                    <div className="bg-gradient-to-br from-cult/10 to-transparent border border-cult/20 p-8 rounded-3xl backdrop-blur-sm relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-32 h-32 bg-cult/20 blur-[50px] rounded-full"></div>
                      <h4 className="text-[10px] text-cult/80 font-bold tracking-[0.2em] uppercase mb-2 relative z-10">Active Guardrails</h4>
                      <p className="text-2xl font-black text-white capitalize relative z-10">
                        {getGuardrailsText()}
                      </p>
                    </div>
                  </div>
                </div>

                {/* AI Architect Chat UI Frame */}
                <div className="bg-[#0a0a0a] border border-white/10 rounded-3xl flex flex-col h-[500px] overflow-hidden shadow-2xl relative flex-1">
                  <div className="flex items-center justify-between px-8 py-6 border-b border-white/5 bg-white/[0.02]">
                      <h2 className="text-sm font-black uppercase tracking-widest text-white">AI Fitness Coach</h2>
                      <div className="flex items-center gap-2 text-[10px] font-bold tracking-widest text-green-400 uppercase">
                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span> Secure
                      </div>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto p-8 space-y-6 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                    {messages.map((msg, i) => (
                      <div key={i} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] p-4 rounded-2xl ${msg.sender === 'user' ? 'bg-cult text-white rounded-br-sm' : 'bg-white/10 text-white/90 rounded-bl-sm border border-white/5'}`}>
                          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                          
                          {/* THE EXECUTION TIMER */}
                          {msg.sender === 'ai' && msg.time_taken !== undefined && (
                            <div className="mt-3 pt-2 border-t border-white/5 flex items-center gap-2 text-[9px] text-white/30 font-bold tracking-widest uppercase">
                              <span className="w-1 h-1 bg-green-500 rounded-full animate-pulse"></span>
                              Engine Execution: {msg.time_taken}s
                            </div>
                          )}

                          {/* THE APPROVAL BUTTONS */}
                          {msg.require_approval && i === messages.length - 1 && !isThinking && (
                            <div className="flex gap-3 mt-4 pt-4 border-t border-white/10">
                              <button 
                                onClick={() => sendMessageToAI("approve")} 
                                className="flex-1 py-2 bg-green-500/10 text-green-400 hover:bg-green-500 hover:text-white text-xs font-black uppercase tracking-widest rounded-lg transition-colors border border-green-500/30"
                              >
                                Approve Sync
                              </button>
                              <button 
                                onClick={() => sendMessageToAI("reject")} 
                                className="flex-1 py-2 bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white text-xs font-black uppercase tracking-widest rounded-lg transition-colors border border-red-500/30"
                              >
                                Discard
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {isThinking && (
                      <div className="flex justify-start">
                        <div className="bg-white/5 border border-white/5 p-4 rounded-2xl rounded-bl-sm flex gap-2 items-center">
                          <span className="w-2 h-2 bg-cult rounded-full animate-pulse"></span>
                          <span className="w-2 h-2 bg-cult rounded-full animate-pulse delay-75"></span>
                          <span className="w-2 h-2 bg-cult rounded-full animate-pulse delay-150"></span>
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>
                  
                  <div className="p-6 bg-white/[0.02] border-t border-white/5">
                    <form onSubmit={handleSendMessage} className="flex gap-4">
                      <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".csv, .txt, image/*" />
                      <button type="button" onClick={() => fileInputRef.current?.click()} className="w-12 h-12 flex-shrink-0 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors text-white/50 hover:text-cult">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                      </button>
                      <input type="text" value={inputStr} onChange={e => setInputStr(e.target.value)} placeholder="Ask a question or request a routine..." className="flex-1 bg-black/50 border border-white/10 rounded-xl px-6 text-sm text-white focus:outline-none focus:border-cult transition-colors" />
                      {isThinking ? (
                        <div className="flex gap-2">
                          {/* THE EMOJI PROCESSING BADGE */}
                          <div className="px-6 py-3 bg-cult/10 border border-cult/30 text-cult font-black uppercase tracking-widest text-xs rounded-xl flex items-center gap-3 shadow-[0_0_15px_rgba(255,50,120,0.2)]">
                            <span className="text-lg w-6 text-center">{fitnessEmoji}</span>
                            <span>Computing...</span>
                          </div>
                          <button type="button" onClick={handleStopProcess} className="px-6 py-3 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/50 font-black uppercase tracking-widest text-xs rounded-xl transition-all shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                            Abort
                          </button>
                        </div>
                      ) : (
                        <button type="submit" disabled={!inputStr.trim()} className="px-8 py-3 bg-cult hover:bg-cult-hover disabled:opacity-50 text-white font-black uppercase tracking-widest text-xs rounded-xl transition-all shadow-[0_0_15px_rgba(255,50,120,0.2)]">
                          Send
                        </button>
                      )}
                    </form>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div key="routine" variants={tabContentVariants} initial="initial" animate="animate" exit="exit" className="w-full flex-1 flex flex-col overflow-hidden">
                {isThinking ? (
                  // NEURAL SKELETON LOADER & MASSIVE TEXT
                  <div className="w-full flex-1 flex flex-col relative p-2 overflow-hidden">
                    
                    {/* THE GLOWING NEURAL TYPOGRAPHY */}
                    <div className="flex justify-center items-center gap-4 mb-8 relative z-10">
                      <div className="w-6 h-6 border-4 border-cult border-t-transparent rounded-full animate-spin shadow-[0_0_15px_rgba(255,50,120,0.8)]"></div>
                      <h2 className="text-xl md:text-2xl font-black uppercase tracking-[0.4em] text-white drop-shadow-[0_0_20px_rgba(255,50,120,0.9)] animate-pulse">
                        Neural Matrix Calculating...
                      </h2>
                    </div>
                    
                    {/* The Skeleton Cards */}
                    <div className="w-full flex-1 flex gap-6 overflow-hidden items-start relative">
                      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cult/10 to-transparent h-[200%] w-full animate-scan z-50 pointer-events-none"></div>
                      
                      {[1, 2, 3, 4, 5].map(i => (
                        <div key={i} className="min-w-[310px] h-[500px] bg-[#0a0a0a] border border-white/5 rounded-2xl p-6 flex flex-col relative overflow-hidden shadow-xl">
                          <div className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer"></div>
                          <div className="w-32 h-6 bg-white/10 rounded mb-2"></div>
                          <div className="w-20 h-3 bg-cult/30 rounded mb-8"></div>
                          <div className="space-y-4 flex-1">
                             {[1, 2, 3, 4].map(j => (
                               <div key={j} className="w-full h-24 bg-white/5 rounded-xl border border-white/5"></div>
                             ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : !hasActiveRoutine ? (
                  // OFFLINE STATE
                  <div className="w-full flex-1 flex flex-col items-center justify-center text-center border-2 border-dashed border-white/5 rounded-3xl bg-black/20 backdrop-blur-sm p-12">
                    <div className="w-14 h-14 rounded-full bg-white/5 flex items-center justify-center mb-6 text-xl border border-white/10 opacity-60">📁</div>
                    <h3 className="text-lg font-black uppercase tracking-widest mb-2">Split Status: Offline</h3>
                    <p className="text-xs text-white/40 uppercase tracking-wider max-w-sm leading-relaxed">
                      No program matrix found in memory. Prompt the AI Architect link inside your Command Center node to compile a training layout.
                    </p>
                  </div>
                ) : (
                  // FRAMER MOTION CASCADE ROUTINE & INLINE EDITOR
                  <div id="printable-routine" className="w-full flex-1 flex flex-col min-h-0 relative">
                    <div className="flex justify-end gap-3 mb-4 px-2 print:hidden">
                      <button onClick={handleDownloadPDF} className="px-5 py-2 bg-blue-500/10 hover:bg-blue-500 text-blue-400 hover:text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-colors border border-blue-500/30">
                        Export PDF 📄
                      </button>
                      {isEditingRoutine ? (
                        <button onClick={handleSaveEditedRoutine} className="px-5 py-2 bg-green-500/10 hover:bg-green-500 text-green-400 hover:text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-colors border border-green-500/30">
                          Save Edits 💾
                        </button>
                      ) : (
                        <button onClick={() => setIsEditingRoutine(true)} className="px-5 py-2 bg-white/5 hover:bg-white/20 text-white/70 hover:text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-colors border border-white/10">
                          Edit Protocol ✏️
                        </button>
                      )}
                      <button onClick={handleWipeRoutine} className="px-5 py-2 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-colors border border-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.2)]">
                        Wipe 🗑️
                      </button>
                    </div>
                    
                    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="w-full flex-1 flex gap-6 overflow-x-auto pb-4 items-start relative select-none [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/10 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-cult/40 transition-colors px-2 print:flex-col print:overflow-visible">
                      {routineData.map((day, dayIdx) => (
                        <motion.div variants={cardVariant} key={dayIdx} className="min-w-[310px] bg-[#0a0a0a] border border-white/10 rounded-2xl p-6 flex flex-col shadow-xl print-day-card">
                          <div className="mb-5 flex justify-between items-start">
                            <div>
                              <h3 className="text-xl font-black uppercase tracking-wider">{day.day_of_week}</h3>
                              <p className="text-[10px] text-cult font-bold uppercase tracking-widest mt-1 print:text-black">{day.focus_area}</p>
                            </div>
                          </div>
                          
                          <div className="space-y-3 flex-1">
                            {day.exercises?.map((ex, exIdx) => (
                              <div key={exIdx} className="bg-white/[0.02] p-4 rounded-xl border border-white/5 hover:border-white/20 transition-all cursor-pointer group print-exercise-row">
                                {isEditingRoutine ? (
                                  <div className="flex flex-col gap-2 relative">
                                    {/* THE DELETE EXERCISE BUTTON */}
                                    <button onClick={() => handleDeleteExercise(dayIdx, exIdx)} className="absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full text-xs flex items-center justify-center hover:bg-red-600 shadow-lg z-10" title="Delete Exercise">✕</button>
                                    
                                    <input type="text" value={ex.name} onChange={(e) => handleExerciseChange(dayIdx, exIdx, 'name', e.target.value)} className="w-full bg-black/50 border border-white/20 px-2 py-1 rounded text-sm font-bold text-white outline-none focus:border-cult" />
                                    <div className="flex gap-2">
                                      <input type="text" value={ex.sets} onChange={(e) => handleExerciseChange(dayIdx, exIdx, 'sets', e.target.value)} className="w-1/3 bg-black/50 border border-white/20 px-2 py-1 rounded text-[11px] text-white outline-none focus:border-cult" placeholder="Sets" />
                                      <input type="text" value={ex.reps} onChange={(e) => handleExerciseChange(dayIdx, exIdx, 'reps', e.target.value)} className="w-2/3 bg-black/50 border border-white/20 px-2 py-1 rounded text-[11px] text-white outline-none focus:border-cult" placeholder="Reps" />
                                    </div>
                                    <textarea value={ex.explanation} onChange={(e) => handleExerciseChange(dayIdx, exIdx, 'explanation', e.target.value)} className="w-full bg-black/50 border border-white/20 px-2 py-1 rounded text-[10px] text-white outline-none focus:border-cult resize-none h-16" placeholder="Explanation" />
                                  </div>
                                ) : (
                                  <>
                                    <h4 className="font-bold text-sm text-white group-hover:text-cult transition-colors leading-tight break-words whitespace-normal">{ex.name}</h4>
                                    <div className="flex gap-4 mt-2 text-white/40 font-bold tracking-widest uppercase text-[11px]">
                                      <span>{ex.sets} Sets</span>
                                      <span className="break-words whitespace-normal flex-1">{ex.reps}</span>
                                    </div>
                                    <p className="text-[10px] text-white/30 mt-3 leading-relaxed hidden group-hover:block transition-all border-t border-white/5 pt-2 break-words whitespace-normal print:block print:text-black">
                                      {ex.explanation}
                                    </p>
                                  </>
                                )}
                                </div>
                              ))}
                            </div>
                            
                            {/* THE ADD EXERCISE BUTTON */}
                            {isEditingRoutine && (
                              <button onClick={() => handleAddExercise(dayIdx)} className="mt-4 w-full py-2 border-2 border-dashed border-white/20 text-white/50 text-xs font-bold uppercase tracking-widest rounded-xl hover:border-cult hover:text-cult transition-colors">
                                + Add Movement
                              </button>
                            )}
                            
                          </motion.div>
                        ))}
                    </motion.div>
                  </div> 
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      {/* --- PROFILE EDIT MODAL --- */}
      <AnimatePresence>
        {showEditModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md overflow-y-auto py-10">
            <motion.div initial={{ scale: 0.93, y: 30, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.93, y: 30, opacity: 0 }} transition={{ type: "spring", damping: 16 }} className="bg-surfaceElevated border border-white/10 p-8 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.8)] w-[460px] flex flex-col relative overflow-hidden my-auto">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[length:100%_4px] pointer-events-none"></div>
              
              <div className="flex justify-between items-start mb-6 relative z-10">
                <div>
                  <h3 className="text-2xl font-black uppercase tracking-widest mb-1">Edit Protocol</h3>
                  <p className="text-white/40 text-[10px] tracking-[0.2em] uppercase">Update Neural Node Baseline</p>
                </div>
                <button onClick={() => setShowEditModal(false)} className="text-white/40 hover:text-white text-xl p-1">✕</button>
              </div>

              <form onSubmit={handleSaveProfile} className="w-full flex flex-col gap-5 relative z-10 text-left">
                
                <div className="flex gap-4 items-end">
                  <div className="relative group cursor-pointer w-20 h-20 flex-shrink-0" onClick={() => editFileRef.current.click()}>
                    <input type="file" ref={editFileRef} onChange={handleEditImageConversion} className="hidden" accept="image/*" />
                    <div className="w-full h-full rounded-full overflow-hidden border-2 border-white/20 group-hover:border-cult transition-colors">
                      {editForm.avatar && editForm.avatar.startsWith('data:image') ? (
                        <img src={editForm.avatar} alt="Avatar" className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center font-black text-2xl text-white" style={{ backgroundColor: editForm.avatar || '#FF3278' }}>
                          {editForm.name ? editForm.name.charAt(0).toUpperCase() : "U"}
                        </div>
                      )}
                    </div>
                    <div className="absolute inset-0 bg-black/60 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <span className="text-xs font-bold text-white uppercase">Upload</span>
                    </div>
                  </div>

                  <div className="flex-1">
                    <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-1 block">Athlete Identity</label>
                    <input required type="text" value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm" />
                  </div>
                </div>

                <div>
                  <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-1 block">Training Protocol</label>
                  <select value={editForm.style} onChange={e => setEditForm({...editForm, style: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm cursor-pointer">
                    <option value="Bodybuilding">Hypertrophy / Bodybuilding</option>
                    <option value="Powerlifting">Strength / Powerlifting</option>
                    <option value="Calisthenics">Calisthenics / Bodyweight</option>
                    <option value="Yoga">Yoga / Mobility Matrix</option>
                    <option value="Athletic">Athletic Performance</option>
                    <option value="General">General Fitness Training</option>
                    <option value="Custom">Other / Custom Protocol...</option>
                  </select>
                </div>

                {/* Inline Fallback Input Field for Custom entries */}
                {editForm.style === "Custom" && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
                    <label className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-1 block">Enter Custom Protocol Name</label>
                    <input required type="text" value={editForm.customStyle} onChange={e => setEditForm({...editForm, customStyle: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm" placeholder="e.g. Olympic Weightlifting" />
                  </motion.div>
                )}

                <div>
                  <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-1 block">Experience Baseline</label>
                  <select value={editForm.experience} onChange={e => setEditForm({...editForm, experience: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm cursor-pointer">
                    <option value="Beginner">Beginner</option>
                    <option value="Intermediate">Intermediate</option>
                    <option value="Advanced">Advanced</option>
                    <option value="Elite">Elite</option>
                  </select>
                </div>

                <div className="mt-4 border-t border-white/10 pt-6">
                  <button type="submit" className="w-full py-3.5 bg-cult text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-cult-hover shadow-[0_0_20px_rgba(255,50,120,0.3)] transition-all active:scale-95">
                    Save Protocol Updates
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}