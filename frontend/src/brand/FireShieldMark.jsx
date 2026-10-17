import React, { useEffect, useRef } from "react";
import { createFireShield } from "./fireShieldRenderer.js";
import "./fireShield.css";

export default function FireShieldMark() {
  const buttonRef = useRef(null);
  const rotorRef = useRef(null);
  const animationRef = useRef(null);

  useEffect(() => {
    let animation;
    try {
      animation = createFireShield(buttonRef.current, rotorRef.current);
      animationRef.current = animation;
    } catch {
      // Keep the static brand visible if canvas rendering is unavailable.
    }
    return () => {
      animationRef.current = null;
      animation?.dispose();
    };
  }, []);

  return (
    <button
      ref={buttonRef}
      className="fireShieldMark"
      type="button"
      aria-label="Animate CityShield fire shield"
      onPointerEnter={(event) => {
        if (event.pointerType !== "touch") animationRef.current?.play();
      }}
      onClick={() => animationRef.current?.play()}
    >
      <img
        className="fireShieldMark__fallback"
        src={`${import.meta.env.BASE_URL}fire-shield.svg`}
        alt=""
        aria-hidden="true"
        width="54"
        height="65"
      />
      <span className="fireShieldMark__perspective" aria-hidden="true">
        <span className="fireShieldMark__lift">
          <span ref={rotorRef} className="fireShieldMark__rotor" />
        </span>
      </span>
    </button>
  );
}
