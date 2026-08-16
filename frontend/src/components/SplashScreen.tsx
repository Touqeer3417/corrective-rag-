import { useState, useEffect, useRef } from 'react';
import { Brain, Zap, Sparkles, Loader2, Cpu, Database, Globe, Shield } from 'lucide-react';

interface SplashScreenProps {
  onComplete: () => void;
}

const COLORS = [
  '#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#f43f5e',
  '#ec4899', '#3b82f6', '#a855f7'
];

const STATUS_MESSAGES = [
  'Initializing neural network...',
  'Loading vector database...',
  'Calibrating retrieval models...',
  'Optimizing query pipelines...',
  'Ready to launch',
];

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const [phase, setPhase] = useState<'enter' | 'idle' | 'exit'>('enter');
  const [progress, setProgress] = useState(0);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);

  // ─── Mouse parallax ───
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      setMousePos({
        x: (e.clientX / window.innerWidth - 0.5) * 2,
        y: (e.clientY / window.innerHeight - 0.5) * 2,
      });
    };
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  // ─── Particle Canvas ───
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    type Particle = {
      x: number; y: number; z: number;
      vx: number; vy: number; vz: number;
      size: number; alpha: number; color: string;
      pulse: number; pulseSpeed: number;
      type: 'dot' | 'ring' | 'cross';
    };

    const particles: Particle[] = [];
    for (let i = 0; i < 100; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        z: Math.random() * 1000,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        vz: (Math.random() - 0.5) * 1.5,
        size: Math.random() * 3 + 1,
        alpha: Math.random() * 0.5 + 0.2,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.02 + 0.01,
        type: (['dot', 'ring', 'cross'] as const)[Math.floor(Math.random() * 3)],
      });
    }

    let frame = 0;
    const animate = () => {
      frame++;
      ctx.fillStyle = 'rgba(2, 6, 23, 0.12)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      particles.sort((a, b) => b.z - a.z);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        p.z += p.vz;
        p.pulse += p.pulseSpeed;

        if (p.x < -50) p.x = canvas.width + 50;
        if (p.x > canvas.width + 50) p.x = -50;
        if (p.y < -50) p.y = canvas.height + 50;
        if (p.y > canvas.height + 50) p.y = -50;
        if (p.z < 0) { p.z = 1000; p.vz = Math.abs(p.vz); }
        if (p.z > 1000) { p.z = 0; p.vz = -Math.abs(p.vz); }

        const scale = 1 - (p.z / 1000) * 0.7;
        const pulseSize = p.size * scale + Math.sin(p.pulse) * 1.2 * scale;
        const alpha = (p.alpha + Math.sin(p.pulse) * 0.1) * scale;

        ctx.save();
        ctx.globalAlpha = Math.max(0, Math.min(1, alpha));

        if (p.type === 'dot') {
          ctx.beginPath();
          ctx.arc(p.x, p.y, Math.max(0.5, pulseSize), 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(p.x, p.y, pulseSize * 3, 0, Math.PI * 2);
          const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, pulseSize * 3);
          g.addColorStop(0, p.color + '25');
          g.addColorStop(1, 'transparent');
          ctx.fillStyle = g;
          ctx.fill();
        } else if (p.type === 'ring') {
          ctx.beginPath();
          ctx.arc(p.x, p.y, pulseSize * 1.5, 0, Math.PI * 2);
          ctx.strokeStyle = p.color;
          ctx.lineWidth = 0.8 * scale;
          ctx.stroke();
        } else if (p.type === 'cross') {
          ctx.strokeStyle = p.color;
          ctx.lineWidth = 0.8 * scale;
          const s = pulseSize * 1.8;
          ctx.beginPath();
          ctx.moveTo(p.x - s, p.y);
          ctx.lineTo(p.x + s, p.y);
          ctx.moveTo(p.x, p.y - s);
          ctx.lineTo(p.x, p.y + s);
          ctx.stroke();
        }

        ctx.restore();
      }

      // Connection lines
      for (let i = 0; i < particles.length; i += 2) {
        for (let j = i + 1; j < particles.length; j += 2) {
          const p1 = particles[i];
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 180) {
            const avgZ = (p1.z + p2.z) / 2;
            const s = 1 - (avgZ / 1000) * 0.8;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(148, 163, 184, ${0.1 * (1 - dist / 180) * s})`;
            ctx.lineWidth = 0.4 * s;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Data streams
      if (frame % 4 === 0) {
        for (let i = 0; i < 3; i++) {
          const sx = Math.random() * canvas.width;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(6, 182, 212, ${Math.random() * 0.08})`;
          ctx.lineWidth = 0.8;
          ctx.moveTo(sx, 0);
          ctx.lineTo(sx + (Math.random() - 0.5) * 80, canvas.height);
          ctx.stroke();
        }
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  // ─── Progress timing ───
  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) { clearInterval(interval); return 100; }
        const inc = p < 30 ? 1.8 : p < 60 ? 1.1 : p < 85 ? 0.7 : 0.35;
        return Math.min(100, p + inc);
      });
    }, 40);

    const t1 = setTimeout(() => setPhase('idle'), 600);
    const t2 = setTimeout(() => setPhase('exit'), 3000);
    const t3 = setTimeout(() => onComplete(), 3800);

    return () => {
      clearInterval(interval);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [onComplete]);

  const msgIndex = Math.min(Math.floor(progress / 20), 4);
  const currentMsg = STATUS_MESSAGES[msgIndex];

  const isEnter = phase === 'enter';
  const isExit = phase === 'exit';

  return (
    <div
      className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden ${
        isExit ? 'opacity-0 scale-125 blur-sm' : 'opacity-100 scale-100'
      }`}
      style={{
        transition: 'all 1.5s cubic-bezier(0.4, 0, 0.2, 1)',
        background: 'radial-gradient(ellipse at center, #0f172a 0%, #020617 50%, #000000 100%)',
      }}
    >
      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none"
        style={{
          opacity: isEnter ? 0 : 1,
          transition: 'opacity 1.2s ease',
          transform: `translate(${mousePos.x * -12}px, ${mousePos.y * -12}px)`,
        }}
      />

      {/* Perspective Grid */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          opacity: isEnter ? 0 : 0.15,
          transition: 'opacity 1.2s ease',
          backgroundImage: `
            linear-gradient(rgba(6, 182, 212, 0.12) 1px, transparent 1px),
            linear-gradient(90deg, rgba(6, 182, 212, 0.12) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
          transform: `perspective(600px) rotateX(55deg) translateY(-80px) translateZ(-250px) translateX(${mousePos.x * 15}px)`,
          transformOrigin: 'center top',
        }}
      />

      {/* Radial glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full animate-pulse"
          style={{
            background: 'radial-gradient(circle, rgba(6,182,212,0.07) 0%, transparent 70%)',
            filter: 'blur(120px)',
            animationDuration: '4s',
          }}
        />
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full animate-pulse"
          style={{
            background: 'radial-gradient(circle, rgba(139,92,246,0.05) 0%, transparent 70%)',
            filter: 'blur(100px)',
            animationDuration: '3s',
            animationDelay: '1s',
          }}
        />
      </div>

      {/* Floating icons */}
      <div
        className="absolute top-[18%] left-[12%] text-cyan-500/15"
        style={{
          animation: 'float 3s ease-in-out infinite',
          transform: `translate(${mousePos.x * 25}px, ${mousePos.y * 25}px)`,
        }}
      >
        <Cpu size={28} />
      </div>
      <div
        className="absolute top-[22%] right-[12%] text-violet-500/15"
        style={{
          animation: 'float 4s ease-in-out infinite 0.5s',
          transform: `translate(${mousePos.x * -20}px, ${mousePos.y * 20}px)`,
        }}
      >
        <Database size={24} />
      </div>
      <div
        className="absolute bottom-[22%] left-[12%] text-emerald-500/15"
        style={{
          animation: 'float 3.5s ease-in-out infinite 1s',
          transform: `translate(${mousePos.x * 18}px, ${mousePos.y * -18}px)`,
        }}
      >
        <Globe size={22} />
      </div>
      <div
        className="absolute bottom-[18%] right-[10%] text-amber-500/15"
        style={{
          animation: 'float 4.5s ease-in-out infinite 1.5s',
          transform: `translate(${mousePos.x * -30}px, ${mousePos.y * -30}px)`,
        }}
      >
        <Shield size={26} />
      </div>

      {/* Main Content */}
      <div
        className={`relative text-center ${
          isEnter ? 'opacity-0 translate-y-10 blur-sm' : isExit ? 'opacity-0 scale-90 blur-md' : 'opacity-100 translate-y-0 blur-0'
        }`}
        style={{
          transition: 'all 1.2s cubic-bezier(0.4, 0, 0.2, 1)',
          transform: isEnter
            ? `translateY(40px) translate(${mousePos.x * 6}px, ${mousePos.y * 6}px)`
            : isExit
            ? 'scale(0.9)'
            : `translate(${mousePos.x * 6}px, ${mousePos.y * 6}px)`,
        }}
      >
        {/* Logo Ring */}
        <div className="relative w-36 h-36 mx-auto mb-8">
          <div className="absolute inset-0 rounded-full border border-cyan-500/12 animate-[spin_10s_linear_infinite]" />
          <div className="absolute inset-2 rounded-full border border-violet-500/12 animate-[spin_7s_linear_infinite_reverse]" />
          <div className="absolute inset-4 rounded-full border border-emerald-500/12 animate-[spin_5s_linear_infinite]" />
          <div className="absolute inset-6 rounded-full border border-amber-500/8 animate-[spin_9s_linear_infinite_reverse]" />

          {/* Orbit dots */}
          <div className="absolute inset-0 animate-[spin_3.5s_linear_infinite]">
            <div
              className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full"
              style={{ background: '#06b6d4', boxShadow: '0 0 8px rgba(6,182,212,0.6)' }}
            />
          </div>
          <div className="absolute inset-0 animate-[spin_4.5s_linear_infinite_reverse]">
            <div
              className="absolute bottom-0 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full"
              style={{ background: '#8b5cf6', boxShadow: '0 0 8px rgba(139,92,246,0.6)' }}
            />
          </div>

          {/* Glow */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-20 h-20 rounded-full animate-pulse"
              style={{
                background: 'rgba(6,182,212,0.12)',
                filter: 'blur(20px)',
                animationDuration: '2s',
              }}
            />
          </div>

          {/* Icon */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative">
              <div
                className="absolute inset-0 rounded-full animate-ping"
                style={{
                  background: 'rgba(6,182,212,0.15)',
                  width: '60px',
                  height: '60px',
                  margin: '-6px',
                  animationDuration: '3s',
                }}
              />
              <Brain size={52} className="text-cyan-300 relative z-10" style={{ filter: 'drop-shadow(0 0 12px rgba(6,182,212,0.4))' }} />
              <Sparkles
                size={18}
                className="absolute -top-2 -right-2 text-violet-300"
                style={{ animation: 'bounce 2s infinite', filter: 'drop-shadow(0 0 8px rgba(139,92,246,0.4))' }}
              />
              <Zap
                size={14}
                className="absolute -bottom-1 -left-2 text-amber-300"
                style={{ animation: 'pulse 2s infinite', filter: 'drop-shadow(0 0 8px rgba(245,158,11,0.4))' }}
              />
              <div
                className="absolute -top-1 -left-3 w-2 h-2 rounded-full animate-ping"
                style={{ background: '#10b981', animationDuration: '2.5s' }}
              />
            </div>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-6xl md:text-8xl font-black tracking-tighter mb-3">
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage: 'linear-gradient(90deg, #67e8f9, #c4b5fd, #6ee7b7, #67e8f9)',
              backgroundSize: '300% 100%',
              animation: 'gradientShift 4s ease infinite',
            }}
          >
            CRAG
          </span>
        </h1>

        {/* Subtitle */}
        <div className="overflow-hidden mb-1">
          <p className="text-xl md:text-2xl text-slate-300 font-light tracking-wide">
            <span className="inline-block" style={{ animation: 'slideUp 0.5s ease-out 0.3s both' }}>Intelligent</span>{' '}
            <span className="inline-block" style={{ animation: 'slideUp 0.5s ease-out 0.5s both' }}>Document</span>{' '}
            <span className="inline-block" style={{ animation: 'slideUp 0.5s ease-out 0.7s both' }}>Search</span>
          </p>
        </div>

        <p
          className="text-xs text-slate-500 tracking-[0.25em] uppercase mb-10"
          style={{ animation: 'fadeIn 1.2s ease-out 1s both' }}
        >
          Powered by Retrieval Augmented Generation
        </p>

        {/* Progress */}
        <div className="w-72 mx-auto">
          <div className="h-1.5 bg-slate-800/70 rounded-full overflow-hidden border border-slate-700/20">
            <div
              className="h-full rounded-full relative overflow-hidden"
              style={{
                width: `${progress}%`,
                transition: 'width 0.2s ease-out',
                backgroundImage: 'linear-gradient(90deg, #06b6d4, #8b5cf6, #10b981, #06b6d4)',
                backgroundSize: '200% 100%',
                animation: 'gradientShift 2s linear infinite',
              }}
            >
              <div
                className="absolute inset-0"
                style={{
                  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
                  animation: 'shimmer 1.5s infinite',
                }}
              />
            </div>
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-xs text-slate-500 flex items-center gap-1">
              <Loader2 size={11} className="animate-spin" />
              {currentMsg}
            </span>
            <span className="text-xs text-cyan-400 font-mono font-semibold">{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Loading dots */}
        <div className="flex justify-center gap-2.5 mt-8">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="w-2.5 h-2.5 rounded-full"
              style={{
                animation: `bounce 0.9s infinite`,
                animationDelay: `${i * 0.12}s`,
                background: `linear-gradient(135deg, ${COLORS[i % COLORS.length]}, ${COLORS[(i + 1) % COLORS.length]})`,
                boxShadow: `0 0 8px ${COLORS[i % COLORS.length]}30`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Corner decorations */}
      <div className="absolute top-5 left-5 w-20 h-20 border-l border-t border-cyan-500/15 rounded-tl-xl" />
      <div className="absolute top-5 left-5 w-6 h-6 border-l-2 border-t-2 border-cyan-400/30 rounded-tl-md" />
      <div className="absolute bottom-5 right-5 w-20 h-20 border-r border-b border-violet-500/15 rounded-br-xl" />
      <div className="absolute bottom-5 right-5 w-6 h-6 border-r-2 border-b-2 border-violet-400/30 rounded-br-md" />
      <div className="absolute top-5 right-5 w-20 h-20 border-r border-t border-emerald-500/15 rounded-tr-xl" />
      <div className="absolute bottom-5 left-5 w-20 h-20 border-l border-b border-amber-500/15 rounded-bl-xl" />

      {/* Scan lines */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          opacity: 0.025,
          background: 'repeating-linear-gradient(0deg, transparent, transparent 3px, rgba(6,182,212,0.2) 3px, rgba(6,182,212,0.2) 6px)',
        }}
      />

      {/* Version */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 text-xs text-slate-600 tracking-[0.3em] uppercase flex items-center gap-2">
        <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
        v2.0 · System Ready
      </div>

      {/* Inline keyframes */}
      <style>{`
        @keyframes gradientShift {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
      `}</style>
    </div>
  );
}