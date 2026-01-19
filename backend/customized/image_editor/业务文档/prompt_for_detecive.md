<purpose>\n检测图片内容是否合规，是否存在暴力，色情这种不合规内容以及图片内容的主体是不是动物, 且不能包括人类。\n</purpose>\n\n<options for false reason>\n- A: 图片包含暴力内容\n- B: 图片包含色情内容\n- C: 图片主体不是动物\n- D: 图片包含人类\n- E: 图片质量过低（分辨率或清晰度不足）\n- F: 图片包含多个主体\n</options>\n\n<output rules>\noutput content must exactly be json WITHOUT ``` marks: \n{\n\t'object_is_only_animal': boolean,\n\t'reason_for_false': option-value\n}\n</output rules>







oil painting, impasto palette knife, a lively and natural pet, exact same pose, rich and warm saturated colors, clean white background #ffffff


Keep the pet exactly same action or pose. Oil painting in a style of thick lines and flat application, creating a strong visual impact, with a clean, pure white background. Features include rough brushstrokes, bold and natural lines, and a maximalist approach with intricate, frenzied, and intense brushwork.Broad strokes are used to generalize the effect of hair or fur, presented in a close-up shot.