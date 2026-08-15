import { useState, useEffect, useRef } from 'react';
import { Brain, Zap, Sparkles } from 'lucide-react';

interface SplashScreenProps {
  onComplete: () => void;
}

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const [phase, setPhase] = useState<'enter' | 'idle' | 'exit'>('enter');
  const [progress, setProgress] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number>(0);

  // Particle animation
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

    const particles: Array<{
      x: number; y: number; vx: number; vy: number;
      size: number; alpha: number; color: string;
      pulse: number; pulseSpeed: number;
    }> = [];

    const colors = ['#06b6d4', '#8b5cf6', '#10b981', '#f59e0b', '#f43f5e'];
    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 3 + 1,
        alpha: Math.random() * 0.5 + 0.2,
        color: colors[Math.floor(Math.random() * colors.length)],
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: Math.random() * 0.02 + 0.01,
      });
    }

    let frame = 0;
    const animate = () => {
      frame++;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw connecting lines
      particles.forEach((p, i) => {
        particles.slice(i + 1).forEach((p2) => {
          const dx = p.x - p2.x;
          const dy = p.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.strokeStyle = `rgba(148, 163, 184, ${0.08 * (1 - dist / 150)})`;
            ctx.lineWidth = 0.5;
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        });
      });

      // Draw particles
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += p.pulseSpeed;

        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        const pulseSize = p.size + Math.sin(p.pulse) * 1;
        const alpha = p.alpha + Math.sin(p.pulse) * 0.1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(0.5, pulseSize), 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
        ctx.fill();

        // Glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, pulseSize * 3, 0, Math.PI * 2);
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, pulseSize * 3);
        gradient.addColorStop(0, p.color + '20');
        gradient.addColorStop(1, 'transparent');
        ctx.fillStyle = gradient;
        ctx.fill();
      });

      ctx.globalAlpha = 1;
      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationRef.current);
    };
  }, []);

  // Progress & phase timing
  useEffect(() => {
    const progressInterval = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(progressInterval);
          return 100;
        }
        return p + 1.5;
      });
    }, 30);

    const idleTimer = setTimeout(() => setPhase('idle'), 600);
    const exitTimer = setTimeout(() => setPhase('exit'), 2800);
    const completeTimer = setTimeout(() => onComplete(), 3500);

    return () => {
      clearInterval(progressInterval);
      clearTimeout(idleTimer);
      clearTimeout(exitTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <div
      className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-slate-950 transition-all duration-1000 ${
        phase === 'exit' ? 'opacity-0 scale-110' : 'opacity-100 scale-100'
      }`}
    >
      {/* Particle Canvas */}
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-none"
        style={{ opacity: phase === 'enter' ? 0 : 1, transition: 'opacity 1s ease' }}
      />

      {/* Radial glow background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-cyan-500/5 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-violet-500/5 rounded-full blur-[100px] animate-pulse" style={{ animationDelay: '0.5s' }} />
      </div>

      {/* Main Content */}
      <div className={`relative text-center transition-all duration-1000 ${
        phase === 'enter' ? 'opacity-0 translate-y-8' : phase === 'exit' ? 'opacity-0 scale-95' : 'opacity-100 translate-y-0'
      }`}>

        {/* Animated Logo Ring */}
        <div className="relative w-32 h-32 mx-auto mb-8">
          {/* Outer rotating ring */}
          <div className="absolute inset-0 rounded-full border border-cyan-500/20 animate-[spin_8s_linear_infinite]" />
          <div className="absolute inset-2 rounded-full border border-violet-500/20 animate-[spin_6s_linear_infinite_reverse]" />
          <div className="absolute inset-4 rounded-full border border-emerald-500/20 animate-[spin_4s_linear_infinite]" />

          {/* Glow behind icon */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-20 h-20 bg-cyan-500/20 rounded-full blur-xl animate-pulse" />
          </div>

          {/* Icon */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="relative">
              <Brain size={48} className="text-cyan-400 relative z-10" />
              <Sparkles size={16} className="absolute -top-2 -right-2 text-violet-400 animate-bounce" style={{ animationDuration: '2s' }} />
              <Zap size={14} className="absolute -bottom-1 -left-2 text-amber-400 animate-pulse" />
            </div>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-5xl md:text-7xl font-black tracking-tight mb-4">
          <span className="bg-gradient-to-r from-cyan-400 via-violet-400 to-emerald-400 bg-clip-text text-transparent animate-gradient">
            CRAG
          </span>
        </h1>

        <p className="text-xl md:text-2xl text-slate-400 font-light tracking-wide mb-2">
          <span className="inline-block animate-[fadeInUp_0.5s_ease-out_0.3s_both]">Intelligent</span>{' '}
          <span className="inline-block animate-[fadeInUp_0.5s_ease-out_0.5s_both]">Document</span>{' '}
          <span className="inline-block animate-[fadeInUp_0.5s_ease-out_0.7s_both]">Search</span>
        </p>

        <p className="text-sm text-slate-600 tracking-widest uppercase mb-10 animate-[fadeIn_1s_ease-out_1s_both]">
          Powered by Retrieval Augmented Generation
        </p>

        {/* Progress Bar */}
        <div className="w-64 mx-auto">
          <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 via-violet-500 to-emerald-500 rounded-full transition-all duration-100 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-xs text-slate-600">Initializing</span>
            <span className="text-xs text-cyan-400 font-mono">{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Loading dots */}
        <div className="flex justify-center gap-2 mt-8">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full bg-cyan-400 animate-bounce"
              style={{ animationDelay: `${i * 0.15}s`, animationDuration: '0.8s' }}
            />
          ))}
        </div>
      </div>

      {/* Corner decorations */}
      <div className="absolute top-8 left-8 w-20 h-20 border-l-2 border-t-2 border-cyan-500/10 rounded-tl-3xl" />
      <div className="absolute bottom-8 right-8 w-20 h-20 border-r-2 border-b-2 border-violet-500/10 rounded-br-3xl" />

      {/* Version tag */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 text-xs text-slate-700 tracking-widest uppercase">
        v2.0 · Ready
      </div>
    </div>
  );
}