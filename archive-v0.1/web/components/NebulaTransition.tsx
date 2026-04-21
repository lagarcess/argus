"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Points, PointMaterial } from "@react-three/drei";
import * as THREE from "three";
import { motion } from "framer-motion";
import { Canvas } from "@react-three/fiber";

function NebulaParticles({ pointerTarget }: { pointerTarget: React.MutableRefObject<THREE.Vector3> }) {
  const ref = useRef<THREE.Points>(null!);

  // Create thousands of points in a spherical distribution
  const count = 3000;
  const { positions, colors } = useMemo(() => {
    const p = new Float32Array(count * 3);
    const c = new Float32Array(count * 3);
    const colorCyan = new THREE.Color("#00f0ff");
    const colorEmerald = new THREE.Color("#00ff9d");

    for (let i = 0; i < count; i++) {
        const r = 2.5 * Math.cbrt(Math.random());
        const theta = Math.random() * 2 * Math.PI;
        const phi = Math.acos(2 * Math.random() - 1);

        p[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        p[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        p[i * 3 + 2] = r * Math.cos(phi);

        // Mix colors based on position
        const mixedColor = colorCyan.clone().lerp(colorEmerald, Math.random());
        c[i * 3] = mixedColor.r;
        c[i * 3 + 1] = mixedColor.g;
        c[i * 3 + 2] = mixedColor.b;
    }
    return { positions: p, colors: c };
  }, []);

  useFrame((state, delta) => {
    if (!ref.current) return;
    ref.current.rotation.x -= delta * 0.03;
    ref.current.rotation.y -= delta * 0.05;

    const targetX = (state.pointer.x * state.viewport.width) / 2;
    const targetY = (state.pointer.y * state.viewport.height) / 2;
    pointerTarget.current.set(targetX, targetY, 0);

    ref.current.position.lerp(pointerTarget.current, delta * 1.5);
  });

  return (
    <group rotation={[0, 0, Math.PI / 4]}>
      <Points ref={ref} positions={positions} colors={colors} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          vertexColors
          size={0.03}
          sizeAttenuation={true}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          opacity={0.6}
        />
      </Points>
    </group>
  );
}
export function NebulaBackground({ className }: { className?: string }) {
  const pointerTarget = useRef(new THREE.Vector3());
  return (
    <div className={`absolute inset-0 z-0 pointer-events-auto ${className || ""}`}>
        <Canvas camera={{ position: [0, 0, 5], fov: 60 }}>
            <ambientLight intensity={0.5} />
            <NebulaParticles pointerTarget={pointerTarget} />
        </Canvas>
    </div>
  );
}
export function NebulaTransition({ isSimulating }: { isSimulating: boolean }) {
  const pointerTarget = useRef(new THREE.Vector3());

  if (!isSimulating) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.8, ease: "easeInOut" }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/90 backdrop-blur-md"
    >
        <div className="absolute inset-0">
            <Canvas camera={{ position: [0, 0, 5], fov: 60 }}>
                <ambientLight intensity={0.5} />
                <NebulaParticles pointerTarget={pointerTarget} />
            </Canvas>
        </div>

        <div className="relative z-10 flex flex-col items-center gap-6">
            {/* Glowing orb in center */}
            <div className="w-16 h-16 rounded-full border-2 border-primary/50 border-t-primary animate-spin shadow-[0_0_30px_rgba(153,247,255,0.6)]" />

            <div className="text-center space-y-2">
               <h2 className="text-3xl font-headline font-black uppercase tracking-widest text-primary drop-shadow-[0_0_10px_rgba(153,247,255,0.4)]">
                 Simulating
               </h2>
               <p className="text-on-surface-variant text-sm tracking-[0.2em] uppercase max-w-xs animate-pulse">
                  Compiling strategy rules • Calculating reality gap • Polling historical data
               </p>
            </div>
        </div>
    </motion.div>
  );
}
