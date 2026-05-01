1. 纯向量检索
Recall@1 = 0.5042，
Recall@3 = 0.7333，
Recall@5 = 0.7875，
Recall@10 = 0.8750，
MRR = 0.6287 

2. Hybrid Search(向量 + 关键词)检索
RRF vector=1.0、keyword=0.5                                                                                                                                         
  - Recall@1 = 0.6083                                                                                                                                                          
  - Recall@3 = 0.7875                                                                                                                                                          
  - Recall@5 = 0.8250                                                                                                                                                          
  - Recall@10 = 0.9250                                                                                                                                                         
  - MRR = 0.7115 
提升幅度：
  - Recall@1: +0.1041                                                                                                                                                              
  - Recall@3: +0.0542                                                                                                                                                              
  - Recall@5: +0.0375                                                                                                                                                              
  - Recall@10: +0.0500                                                                                                                                                             
  - MRR: +0.0828  


3. 加上rerank
加上之前：Recall@1=0.5800，MRR=0.7695  
加上之后：Recall@1=0.7800，MRR=0.8900  