document.querySelectorAll('input[type="password"]').forEach(input => {
 const button=document.createElement('button'); button.type='button';button.className='small-button';button.textContent='◉';button.setAttribute('aria-label','نمایش رمز واردشده');button.setAttribute('aria-pressed','false');
 button.addEventListener('click',()=>{const show=input.type==='password';input.type=show?'text':'password';button.setAttribute('aria-pressed',String(show));button.setAttribute('aria-label',show?'پنهان کردن رمز':'نمایش رمز واردشده');}); input.after(button);
 input.form?.addEventListener('submit',()=>{input.type='password';});
});