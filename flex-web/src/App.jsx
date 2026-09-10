import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { backend } from './api';
import Dashboard from './Dashboard';

export default function App() {
  const [activeView, setActiveView] = useState("gate"); 
  const [profiles, setProfiles] = useState([]);
  const [activeProfile, setActiveProfile] = useState(null); 
  
  const [authData, setAuthData] = useState(null); 
  const [passwordInput, setPasswordInput] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const [showNewModal, setShowNewModal] = useState(false);
  const [newAthlete, setNewAthlete] = useState({ name: '', style: 'Bodybuilding', customStyle: '', user: '', pass: '', color: '#FF3278', avatarFile: null });
  const fileRef = useRef(null);

  // calibration state
  const [calibrationLevel, setCalibrationLevel] = useState("Intermediate");
  const [calibrationFile, setCalibrationFile] = useState(null);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const calibFileRef = useRef(null);

  useEffect(() => {
    if (activeView === "gate") {
      backend.fetch_all_profiles().then(data => setProfiles(data));
    }
  }, [activeView]);

  const handleProfileClick = async (profile) => {
    try {
      const data = await backend.request_profile_login(profile.id);
      if (data.password) {
        setAuthData({ ...data, fullProfile: profile });
        setErrorMsg("");
        setPasswordInput("");
      } else {
        await backend.confirm_authenticated_login(profile.id);
        setActiveProfile(profile);
        setActiveView("dashboard");
      }
    } catch (err) {
      console.error("Login failed:", err);
    }
  };

  const handleProfileDelete = async (e, id) => {
    e.stopPropagation(); // Avoid triggering login routine when clicking cross
    if (!confirm("Are you sure you want to permanently delete this account? This cannot be undone.")) return;
    try {
      await backend.delete_athlete_profile(id);
      setProfiles(prev => prev.filter(p => p.id !== id));
    } catch (err) {
      console.error("Deletion failed:", err);
    }
  };

  const handleImageConversion = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setNewAthlete({ ...newAthlete, avatarFile: reader.result });
    };
    reader.readAsDataURL(file);
  };

  const handleUnlock = async (e) => {
    e.preventDefault();
    if (passwordInput === authData.password) {
      await backend.confirm_authenticated_login(authData.user_id);
      setActiveProfile(authData.fullProfile);
      setAuthData(null); 
      setActiveView("dashboard");
    } else {
      setErrorMsg("ACCESS DENIED. INVALID CREDENTIALS.");
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!newAthlete.name) return;
    
    const generatedId = newAthlete.name.toLowerCase().replace(/\s/g, '');
    const selectedProtocol = newAthlete.style === 'Custom' ? newAthlete.customStyle : newAthlete.style;
    const trackingAvatar = newAthlete.avatarFile || newAthlete.color;
    
    try {
      await backend.register_profile(
        generatedId, newAthlete.name, selectedProtocol, 
        newAthlete.user, newAthlete.pass, trackingAvatar
      );
      
      await backend.confirm_authenticated_login(generatedId);
      setActiveProfile({ id: generatedId, name: newAthlete.name, avatar_color: trackingAvatar, athlete_type: selectedProtocol });
      setShowNewModal(false);
      // Reset initialization object state
      setNewAthlete({ name: '', style: 'Bodybuilding', customStyle: '', user: '', pass: '', color: '#FF3278', avatarFile: null });
      
      // Route to the Calibration Screen
      setActiveView("calibration");
    } catch (err) {
      console.error("Registration failed:", err);
    }
  };

  const handleFinalizeCalibration = async () => {
    setIsCalibrating(true);
    try {
      if (calibrationFile) {
        await backend.upload_workout_log(calibrationFile);
      } else {
        await backend.calibrate_profile(calibrationLevel);
      }
      setActiveView("dashboard");
    } catch (err) {
      console.error("Calibration failed:", err);
    } finally {
      setIsCalibrating(false);
    }
  };

  //  Abort Calibration and clean up incomplete database rows
  const handleAbortCalibration = async () => {
    if (activeProfile && activeProfile.id) {
      try {
        // Recycle the deletion bridge to clear the database entry
        await backend.delete_athlete_profile(activeProfile.id);
        setProfiles(prev => prev.filter(p => p.id !== activeProfile.id));
      } catch (err) {
        console.error("Failed to clean up incomplete profile:", err);
      }
    }
    setActiveProfile(null);
    setActiveView("gate");
  };

  const themeColors = ["#FF3278", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899"];
  const containerVariants = { hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.12, delayChildren: 0.2 } } };
  const itemVariants = { hidden: { opacity: 0, y: 35 }, show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 60, damping: 14 } } };

  if (activeView === "dashboard") {
    return <Dashboard onLogout={() => setActiveView("gate")} initialProfile={activeProfile} />;
  }

  if (activeView === "calibration") {
    return (
      <div className="relative min-h-[100dvh] w-screen bg-surface flex flex-col items-center justify-center font-sans select-none p-6">
        
        {/* CALIBRATION CINEMATIC DATA OVERLAY BACKGROUND */}
        <div className="fixed inset-0 w-full h-full z-0 overflow-hidden pointer-events-none">
          {/* ADDED KEY HERE */}
          <video key="calib-video" autoPlay loop muted playsInline className="absolute top-0 left-0 w-full h-full object-cover opacity-50">
            <source src={`${import.meta.env.BASE_URL}calib-bg.mp4`} type="video/mp4" />
          </video>
          <div className="absolute inset-0 bg-gradient-to-b from-black/50 to-[#050505]"></div>
        </div>

        <div className="noise-overlay fixed"></div>
        <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cult/5 blur-[150px] rounded-full pointer-events-none"></div>

        <motion.div initial={{ scale: 0.95, opacity: 0, y: 20 }} animate={{ scale: 1, opacity: 1, y: 0 }} className="relative z-10 bg-surfaceElevated border border-white/10 p-10 rounded-3xl shadow-2xl w-full max-w-lg flex flex-col">
          <div className="w-12 h-12 bg-white/5 border border-white/10 rounded-full flex items-center justify-center mb-6 text-xl">⚙️</div>
          <h2 className="text-3xl font-black uppercase tracking-tighter mb-2">Data Calibration</h2>
          <p className="text-white/40 text-xs tracking-widest uppercase mb-8 leading-relaxed">Personalize your experience. Import historical logs or set your baseline manually.</p>

          <div className="flex flex-col gap-8">
            {/* FILE UPLOAD ZONE */}
            <div>
              <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-3 block">Option A: Import Historical Data</label>
              <input type="file" ref={calibFileRef} onChange={(e) => setCalibrationFile(e.target.files[0])} className="hidden" accept=".csv, .txt, image/*" />
              <div 
                onClick={() => calibFileRef.current.click()}
                className={`w-full border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all ${calibrationFile ? 'border-cult bg-cult/5' : 'border-white/10 hover:border-white/30 bg-black/20'}`}
              >
                <div className={`text-3xl mb-3 ${calibrationFile ? 'text-cult' : 'text-white/20'}`}>{calibrationFile ? '📄' : '📥'}</div>
                <p className="text-sm font-bold text-white mb-1">{calibrationFile ? calibrationFile.name : 'Upload Workout Logs'}</p>
                <p className="text-[10px] text-white/40 tracking-widest uppercase">{calibrationFile ? 'Ready for ingestion' : 'CSV, TXT, or Screenshots'}</p>
              </div>
            </div>

            {/* MANUAL FALLBACK ZONE */}
            <div className={`transition-opacity ${calibrationFile ? 'opacity-30 pointer-events-none' : 'opacity-100'}`}>
              <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-3 block">Option B: Manual Baseline</label>
              <div className="grid grid-cols-2 gap-3">
                {["Beginner", "Intermediate", "Advanced", "Elite"].map((level) => (
                  <div 
                    key={level}
                    onClick={() => setCalibrationLevel(level)}
                    className={`p-4 rounded-xl border cursor-pointer text-center transition-all ${calibrationLevel === level ? 'border-cult bg-cult/10 text-white' : 'border-white/5 bg-white/[0.02] text-white/50 hover:bg-white/5 hover:border-white/20'}`}
                  >
                    <span className="text-xs font-bold uppercase tracking-wider">{level}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex gap-4 mt-10">
            <button 
              onClick={handleAbortCalibration}
              className="flex-1 py-4 text-xs font-bold uppercase tracking-widest text-white/40 hover:text-white transition-colors"
            >
              Abort
            </button>
            <button 
              onClick={handleFinalizeCalibration}
              disabled={isCalibrating}
              className="flex-[2] py-4 bg-cult text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-cult-hover shadow-[0_0_20px_rgba(255,50,120,0.3)] transition-all active:scale-95 disabled:opacity-50"
            >
              {isCalibrating ? 'Ingesting...' : 'Create and Finalize'}
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="relative min-h-[100dvh] w-screen bg-surface flex flex-col items-center justify-center overflow-y-auto overflow-x-hidden font-sans select-none py-20">
      
      {/* CINEMATIC VIDEO BACKGROUND */}
      <div className="fixed inset-0 w-full h-full z-0 overflow-hidden pointer-events-none">
        {/*  ADDED KEY HERE */}
        <video key="gate-video" autoPlay loop muted playsInline className="absolute top-0 left-0 w-full h-full object-cover opacity-60">
          <source src={`${import.meta.env.BASE_URL}gate-bg.mp4`} type="video/mp4" />
        </video>
        {/* Darkened overlay to make the white text pop, while keeping the video vivid */}
        <div className="absolute inset-0 bg-gradient-to-b from-black/40 via-black/70 to-[#050505]"></div>
      </div>

      <div className="noise-overlay fixed z-0"></div>
      <div className="fixed top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-cult/15 blur-[150px] rounded-full pointer-events-none z-0"></div>

      <motion.div className="relative z-10 flex flex-col items-center text-center w-full max-w-6xl px-6 my-auto" variants={containerVariants} initial="hidden" animate="show">
        <motion.div variants={itemVariants} className="flex items-center gap-3 mb-6">
          <div className="w-3 h-3 bg-cult rounded-full animate-pulse shadow-[0_0_15px_rgba(255,50,120,0.6)]"></div>
          <h2 className="text-sm font-black tracking-[0.3em] uppercase text-transparent bg-clip-text bg-gradient-to-r from-cult to-purple-500">
            FlexRoute: Your AI Fitness Coach
          </h2>
        </motion.div>

        <motion.h1 variants={itemVariants} className="text-6xl md:text-8xl font-black mb-16 tracking-tighter uppercase drop-shadow-2xl leading-none">
          Who is <br/> <span className="text-cult">Training?</span>
        </motion.h1>

        <motion.div variants={itemVariants} className="flex flex-wrap justify-center gap-6 w-full">
          {profiles.map((p) => {
            const isImage = p.avatar_color && p.avatar_color.startsWith('data:image');
            const firstLetter = p.name.charAt(0).toUpperCase();

            return (
              <motion.div key={p.id} onClick={() => handleProfileClick(p)} whileHover={{ scale: 1.05, y: -8 }} whileTap={{ scale: 0.98 }} className="group relative w-56 p-8 rounded-3xl cursor-pointer overflow-hidden border border-white/5 bg-gradient-to-b from-white/[0.08] to-transparent backdrop-blur-md shadow-2xl transition-colors hover:border-cult/50">
                {/* Delete button option */}
                <button 
                  onClick={(e) => handleProfileDelete(e, p.id)}
                  className="absolute top-4 right-4 z-20 w-6 h-6 rounded-full bg-black/40 text-white/40 hover:text-red-400 hover:bg-black/80 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Wipe Profile Row Data"
                >
                  ✕
                </button>
                
                <div className="absolute inset-0 bg-cult/0 group-hover:bg-cult/5 transition-colors duration-500"></div>
                <div className="relative z-10 mb-6 flex justify-center">
                  {isImage ? <img src={p.avatar_color} className="w-20 h-20 rounded-full object-cover border-2 border-white/10 shadow-2xl" alt={p.name} /> : <div className="w-20 h-20 rounded-full flex items-center justify-center text-3xl font-black text-white shadow-2xl border-2 border-white/10" style={{ backgroundColor: p.avatar_color || '#FF3278' }}>{firstLetter}</div>}
                </div>
                <h2 className="relative z-10 text-xl font-black tracking-tight truncate w-full">{p.name}</h2>
                <p className="relative z-10 text-[10px] text-white/40 font-bold uppercase tracking-widest mt-2">{p.username ? 'Secure Link' : 'Open Access'}</p>
              </motion.div>
            );
          })}

          <motion.div onClick={() => setShowNewModal(true)} whileHover={{ scale: 1.05, y: -8 }} whileTap={{ scale: 0.98 }} className="group w-56 p-8 rounded-3xl cursor-pointer border-2 border-dashed border-white/10 hover:border-white/40 flex flex-col items-center justify-center transition-all bg-black/20 backdrop-blur-sm">
            <div className="w-16 h-16 rounded-full border border-white/20 flex items-center justify-center text-2xl text-white/50 mb-6 group-hover:text-white transition-colors">+</div>
            <h2 className="text-sm font-black text-white/70 uppercase tracking-widest group-hover:text-white transition-colors">New Athlete</h2>
          </motion.div>
        </motion.div>
      </motion.div>

      {/* --- LOGIN MODAL --- */}
      <AnimatePresence>
        {authData && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md">
            <motion.div initial={{ scale: 0.93, y: 30, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.93, y: 30, opacity: 0 }} transition={{ type: "spring", damping: 16 }} className="bg-surfaceElevated border border-white/10 p-10 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.8)] w-[400px] flex flex-col items-center text-center relative overflow-hidden">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[length:100%_4px] pointer-events-none"></div>
              <div className="w-12 h-12 rounded-full border-2 border-cult flex items-center justify-center mb-6 shadow-[0_0_15px_rgba(255,50,120,0.4)]"><span className="text-cult font-bold">🔒</span></div>
              <h3 className="text-2xl font-black uppercase tracking-widest mb-2">Secure Link</h3>
              <p className="text-white/50 text-xs tracking-[0.2em] uppercase mb-8">Enter authorization code for {authData.fullProfile?.name}</p>
              <form onSubmit={handleUnlock} className="w-full flex flex-col gap-6 relative z-10">
                <input type="password" autoFocus value={passwordInput} onChange={(e) => setPasswordInput(e.target.value)} className="w-full bg-black/50 border border-white/10 text-center text-2xl tracking-[0.3em] py-4 rounded-xl text-white outline-none focus:border-cult focus:shadow-[0_0_15px_rgba(255,50,120,0.2)] transition-all" placeholder="••••••••" />
                {errorMsg && <p className="text-red-500 text-xs font-bold tracking-widest animate-pulse">{errorMsg}</p>}
                <div className="flex gap-4 mt-4">
                  <button type="button" onClick={() => setAuthData(null)} className="flex-1 py-4 text-xs font-bold uppercase tracking-widest text-white/50 hover:text-white transition-colors">Abort</button>
                  <button type="submit" className="flex-1 py-4 bg-cult text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-cult-hover shadow-[0_0_20px_rgba(255,50,120,0.3)] transition-all active:scale-95">Unlock</button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* --- ADVANCED REGISTRATION MODAL WITH EXTENDED PROTOCOLS & ACCENTS --- */}
      <AnimatePresence>
        {showNewModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md overflow-y-auto py-10">
            <motion.div initial={{ scale: 0.93, y: 30, opacity: 0 }} animate={{ scale: 1, y: 0, opacity: 1 }} exit={{ scale: 0.93, y: 30, opacity: 0 }} transition={{ type: "spring", damping: 16 }} className="bg-surfaceElevated border border-white/10 p-8 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.8)] w-[460px] flex flex-col relative overflow-hidden my-auto">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[length:100%_4px] pointer-events-none"></div>
              
              <h3 className="text-2xl font-black uppercase tracking-widest text-center mb-1 relative z-10">New Athelete</h3>
              <p className="text-white/40 text-[10px] tracking-[0.2em] uppercase text-center mb-6 relative z-10">Configure Training Credentials</p>

              <form onSubmit={handleRegister} className="w-full flex flex-col gap-4 relative z-10 text-left">
                
                {/* Name */}
                <div>
                  <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-1 block">Athlete Identity</label>
                  <input required type="text" value={newAthlete.name} onChange={e => setNewAthlete({...newAthlete, name: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm" placeholder="e.g. Marcus Aurelius" />
                </div>

                {/* Training Styles Mapping Panel */}
                <div>
                  <label className="text-[10px] text-cult font-bold uppercase tracking-widest mb-1 block">Training Style</label>
                  <select value={newAthlete.style} onChange={e => setNewAthlete({...newAthlete, style: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm cursor-pointer">
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
                {newAthlete.style === "Custom" && (
                  <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
                    <label className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-1 block">Enter Custom Protocol Name</label>
                    <input required type="text" value={newAthlete.customStyle} onChange={e => setNewAthlete({...newAthlete, customStyle: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-3 rounded-xl text-white outline-none focus:border-cult transition-all text-sm" placeholder="e.g. Olympic Weightlifting" />
                  </motion.div>
                )}

                {/* Custom Profile Picture or Theme Palette Selection */}
                <div className="border-y border-white/5 py-4 my-2 grid grid-cols-2 gap-4 items-center">
                  <div>
                    <label className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-2 block">Visual Avatar</label>
                    <input type="file" ref={fileRef} onChange={handleImageConversion} className="hidden" accept="image/*" />
                    <button 
                      type="button" 
                      onClick={() => fileRef.current.click()}
                      className="w-full py-2.5 bg-white/5 border border-white/10 rounded-xl text-xs font-bold uppercase tracking-wider text-white hover:bg-white/10 transition-colors truncate px-2"
                    >
                      {newAthlete.avatarFile ? "✓ Photo Configured" : "Upload Image"}
                    </button>
                  </div>
                  
                  <div>
                    <label className="text-[10px] text-white/50 font-bold uppercase tracking-widest mb-2 block">Accent Slate (No Photo)</label>
                    <div className="flex flex-wrap gap-1.5">
                      {themeColors.map(c => (
                        <div 
                          key={c} 
                          onClick={() => setNewAthlete({ ...newAthlete, color: c, avatarFile: null })}
                          className={`w-5 h-5 rounded-full cursor-pointer transition-transform border ${newAthlete.color === c && !newAthlete.avatarFile ? 'scale-125 border-white' : 'border-transparent hover:scale-110'}`}
                          style={{ backgroundColor: c }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Authentication Mapping */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-[10px] text-white/40 font-bold uppercase tracking-widest mb-1 block">Security ID (Optional)</label>
                    <input type="text" value={newAthlete.user} onChange={e => setNewAthlete({...newAthlete, user: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-2.5 rounded-xl text-white outline-none text-xs" placeholder="Username" />
                  </div>
                  <div>
                    <label className="text-[10px] text-white/40 font-bold uppercase tracking-widest mb-1 block">Password (Optional)</label>
                    <input type="password" value={newAthlete.pass} onChange={e => setNewAthlete({...newAthlete, pass: e.target.value})} className="w-full bg-black/50 border border-white/10 px-4 py-2.5 rounded-xl text-white outline-none text-xs" placeholder="Password" />
                  </div>
                </div>

                <div className="flex gap-4 mt-4">
                  <button type="button" onClick={() => setShowNewModal(false)} className="flex-1 py-3.5 text-xs font-bold uppercase tracking-widest text-white/40 hover:text-white transition-colors">Abort</button>
                  <button type="submit" className="flex-[2] py-3.5 bg-cult text-white text-xs font-black uppercase tracking-widest rounded-xl hover:bg-cult-hover shadow-[0_0_20px_rgba(255,50,120,0.3)] transition-all active:scale-95">Continue</button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}