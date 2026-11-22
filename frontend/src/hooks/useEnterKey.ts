import { useEffect, useEffectEvent } from 'react';

/** What uses the Enter key itself: a field being typed in, a focused button, link or choice. */
const OWN_ENTER =
  'input, textarea, select, button, a[href], summary, [contenteditable], [role="button"], [role="link"], [role="menuitem"], [role="option"], [role="combobox"], [role="textbox"], [role="tab"], [role="checkbox"], [role="radio"], [role="switch"]';

function takesEnter(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return false;
  const el = target.closest(OWN_ENTER);
  // a button that went disabled while focused (Run, once it runs) does nothing with it
  return !!el && !el.matches(':disabled');
}

/**
 * The Enter key as the shortcut of a page's Enter button, while `active`: pressed with nothing that
 * takes Enter itself in focus, no modifier, not held down and not ending an IME composition.
 */
export function useEnterKey(active: boolean, onEnter: () => void): void {
  const fire = useEffectEvent(onEnter);
  useEffect(() => {
    if (!active) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || e.repeat || e.isComposing || e.defaultPrevented) return;
      if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return;
      if (takesEnter(e.target)) return;
      e.preventDefault();
      fire();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [active]);
}
