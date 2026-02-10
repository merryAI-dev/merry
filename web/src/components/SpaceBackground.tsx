"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Sphere, MeshDistortMaterial } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";

function AnimatedSphere() {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.getElapsedTime() * 0.2;
      meshRef.current.rotation.y = state.clock.getElapsedTime() * 0.3;
    }
  });

  return (
    <Sphere ref={meshRef} args={[1, 100, 100]} scale={2.5}>
      <MeshDistortMaterial
        color="#001e46"
        attach="material"
        distort={0.3}
        speed={1.5}
        roughness={0.4}
      />
    </Sphere>
  );
}

function Stars() {
  const starsRef = useRef<THREE.Points>(null);

  useFrame(() => {
    if (starsRef.current) {
      starsRef.current.rotation.y += 0.0002;
    }
  });

  const starPositions = new Float32Array(2000 * 3);
  for (let i = 0; i < 2000; i++) {
    const i3 = i * 3;
    starPositions[i3] = (Math.random() - 0.5) * 50;
    starPositions[i3 + 1] = (Math.random() - 0.5) * 50;
    starPositions[i3 + 2] = (Math.random() - 0.5) * 50;
  }

  return (
    <points ref={starsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={starPositions.length / 3}
          array={starPositions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial size={0.05} color="#ffffff" sizeAttenuation transparent opacity={0.8} />
    </points>
  );
}

export function SpaceBackground() {
  return (
    <div className="fixed inset-0 -z-10">
      <Canvas
        camera={{ position: [0, 0, 5], fov: 75 }}
        style={{ background: "radial-gradient(ellipse at center, #0a0e1a 0%, #000000 100%)" }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#0066cc" />
        <AnimatedSphere />
        <Stars />
      </Canvas>
    </div>
  );
}
